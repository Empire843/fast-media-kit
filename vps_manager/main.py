import os
import json
import socket
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import paramiko

app = FastAPI(title="VPS Management Dashboard")

# Thư mục chứa file tĩnh
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount thư mục static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

CONFIG_FILE = BASE_DIR / "config.json"

class ConnectionConfig(BaseModel):
    ip: str
    port: int = 10056
    username: str = "administrator"
    password: str = ""
    # Nếu muốn lưu cấu hình lâu dài
    save_config: bool = True

def get_saved_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def save_config_file(config: dict):
    CONFIG_FILE.write_text(json.dumps(config, indent=4), encoding="utf-8")

def connect_ssh(ip, port, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            hostname=ip,
            port=port,
            username=username,
            password=password,
            timeout=8
        )
        return ssh
    except socket.timeout:
        raise HTTPException(status_code=504, detail="Kết nối đến VPS bị hết thời gian (Timeout). Hãy kiểm tra lại NAT Port và trạng thái VPS.")
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu SSH.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể kết nối SSH: {str(e)}")

def get_ssh_from_saved():
    cfg = get_saved_config()
    if not cfg:
        raise HTTPException(status_code=400, detail="Chưa cấu hình kết nối VPS. Vui lòng kết nối trước.")
    return connect_ssh(cfg["ip"], cfg["port"], cfg["username"], cfg["password"])

@app.get("/", response_class=HTMLResponse)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>Giao diện đang được khởi tạo...</h1>"

@app.post("/api/connect")
def api_connect(config: ConnectionConfig):
    # Thử kết nối trước xem thông tin có đúng không
    ssh = connect_ssh(config.ip, config.port, config.username, config.password)
    ssh.close()
    
    cfg_data = {
        "ip": config.ip,
        "port": config.port,
        "username": config.username,
        "password": config.password
    }
    
    if config.save_config:
        save_config_file(cfg_data)
        
    return {"status": "success", "message": "Kết nối thành công và đã lưu cấu hình!"}

@app.get("/api/config")
def api_get_config():
    cfg = get_saved_config()
    if cfg:
        # Ẩn bớt mật khẩu cho an toàn
        return {
            "ip": cfg["ip"],
            "port": cfg["port"],
            "username": cfg["username"],
            "has_password": bool(cfg["password"])
        }
    return {"ip": "", "port": 10056, "username": "administrator", "has_password": False}

@app.get("/api/status")
def api_status():
    ssh = get_ssh_from_saved()
    try:
        # Lấy Uptime và Load Average
        stdin, stdout, stderr = ssh.exec_command("uptime")
        uptime_out = stdout.read().decode("utf-8").strip()
        
        # Lấy RAM (đơn vị MB)
        stdin, stdout, stderr = ssh.exec_command("free -m")
        ram_lines = stdout.read().decode("utf-8").splitlines()
        ram_info = {}
        if len(ram_lines) > 1:
            parts = ram_lines[1].split()
            # free -m headers: total used free shared buff/cache available
            ram_info = {
                "total": int(parts[1]),
                "used": int(parts[2]),
                "free": int(parts[3]),
                "available": int(parts[6]) if len(parts) > 6 else int(parts[3])
            }
            
        # Lấy Ổ Đĩa (Disk)
        stdin, stdout, stderr = ssh.exec_command("df -h /")
        disk_lines = stdout.read().decode("utf-8").splitlines()
        disk_info = {}
        if len(disk_lines) > 1:
            parts = disk_lines[1].split()
            disk_info = {
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "percent": parts[4].replace("%", "")
            }
            
        # Lấy CPU usage qua top
        stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)'")
        cpu_out = stdout.read().decode("utf-8").strip()
        cpu_percent = 0.0
        # parse: "%Cpu(s):  5.0 us,  2.0 sy..." -> lấy 100 - idle
        try:
            if "id," in cpu_out:
                idle = cpu_out.split("id,")[0].split(",")[-1].strip().split()[0]
                cpu_percent = round(100.0 - float(idle), 1)
        except Exception:
            pass
            
        return {
            "uptime": uptime_out,
            "ram": ram_info,
            "disk": disk_info,
            "cpu": cpu_percent
        }
    finally:
        ssh.close()

@app.get("/api/containers")
def api_containers():
    ssh = get_ssh_from_saved()
    try:
        # Lấy danh sách các container dưới định dạng JSON
        # Một số VPS cần dùng sudo để chạy lệnh docker
        stdin, stdout, stderr = ssh.exec_command("sudo docker ps -a --format '{{json .}}'")
        output = stdout.read().decode("utf-8").strip()
        
        containers = []
        if output:
            for line in output.splitlines():
                try:
                    containers.append(json.loads(line))
                except Exception:
                    pass
        return containers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách container: {str(e)}")
    finally:
        ssh.close()

@app.post("/api/container/action")
def api_container_action(
    name: str = Body(..., embed=True),
    action: str = Body(..., embed=True)
):
    if action not in ["start", "stop", "restart"]:
        raise HTTPException(status_code=400, detail="Hành động không hợp lệ.")
        
    ssh = get_ssh_from_saved()
    try:
        cmd = f"sudo docker {action} {name}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        err = stderr.read().decode("utf-8").strip()
        if err and "warning" not in err.lower():
            raise HTTPException(status_code=500, detail=f"Lỗi thực thi lệnh: {err}")
        return {"status": "success", "message": f"Đã thực hiện lệnh {action} trên container {name}!"}
    finally:
        ssh.close()

@app.get("/api/container/logs")
def api_container_logs(name: str):
    ssh = get_ssh_from_saved()
    try:
        cmd = f"sudo docker logs --tail 150 {name}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        logs = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")
        # Docker logs xuất log ra stderr cũng là bình thường, ghép cả 2 lại
        return {"logs": logs + err}
    finally:
        ssh.close()

@app.get("/api/env")
def api_get_env():
    ssh = get_ssh_from_saved()
    try:
        # Thử đọc file .env trong thư mục fast-media-kit
        cmd = "cat ~/fast-media-kit/.env"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        content = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")
        
        if "No such file" in err:
            # Nếu chưa có, trả về template rỗng
            return {"content": "# Cấu hình dự án Fast Media Kit\nPORT=8000\nTRANSLATION_PROVIDER=aishop24h\n"}
            
        return {"content": content}
    finally:
        ssh.close()

@app.post("/api/env")
def api_save_env(content: str = Body(..., embed=True)):
    ssh = get_ssh_from_saved()
    try:
        # Viết đè nội dung vào file .env
        # Tránh việc dùng các lệnh echo phức tạp bị lỗi ký tự đặc biệt, ta viết qua file tạm
        # Bằng cách sử dụng sftp hoặc tạo file qua heredoc trong bash
        sftp = ssh.open_sftp()
        try:
            # Tạo đường dẫn file .env
            env_path = "/home/administrator/fast-media-kit/.env"
            with sftp.file(env_path, "w") as f:
                f.write(content)
        finally:
            sftp.close()
            
        return {"status": "success", "message": "Đã lưu file .env thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu file: {str(e)}")
    finally:
        ssh.close()

@app.get("/api/files")
def api_list_files(path: str = ""):
    ssh = get_ssh_from_saved()
    try:
        sftp = ssh.open_sftp()
        if not path:
            # Mặc định lấy thư mục home
            path = sftp.normalize(".")
            
        try:
            path = sftp.normalize(path)
            items = sftp.listdir_attr(path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Không thể mở thư mục {path}: {str(e)}")
            
        file_list = []
        import stat
        for item in items:
            is_dir = stat.S_ISDIR(item.st_mode)
            file_list.append({
                "name": item.filename,
                "path": os.path.join(path, item.filename).replace("\\", "/"),
                "is_dir": is_dir,
                "size": item.st_size,
                "modified": item.st_mtime
            })
            
        file_list.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        return {
            "current_path": path,
            "parent_path": os.path.dirname(path).replace("\\", "/") if path != "/" else "",
            "files": file_list
        }
    finally:
        ssh.close()

@app.delete("/api/files")
def api_delete_file(path: str):
    ssh = get_ssh_from_saved()
    try:
        # Xóa đệ quy bằng command line để xử lý được cả thư mục chứa file
        cmd = f"rm -rf '{path}'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        err = stderr.read().decode("utf-8").strip()
        if err:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa: {err}")
        return {"status": "success", "message": "Đã xóa thành công!"}
    finally:
        ssh.close()

@app.post("/api/files/mkdir")
def api_mkdir(
    path: str = Body(..., embed=True),
    name: str = Body(..., embed=True)
):
    ssh = get_ssh_from_saved()
    try:
        sftp = ssh.open_sftp()
        full_path = os.path.join(path, name).replace("\\", "/")
        sftp.mkdir(full_path)
        return {"status": "success", "message": "Đã tạo thư mục thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo thư mục: {str(e)}")
    finally:
        ssh.close()

@app.post("/api/files/create")
def api_create_file(
    path: str = Body(..., embed=True),
    name: str = Body(..., embed=True)
):
    ssh = get_ssh_from_saved()
    try:
        sftp = ssh.open_sftp()
        full_path = os.path.join(path, name).replace("\\", "/")
        with sftp.file(full_path, "w") as f:
            f.write("")
        return {"status": "success", "message": "Đã tạo file thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo file: {str(e)}")
    finally:
        ssh.close()

@app.get("/api/files/content")
def api_get_file_content(path: str):
    ssh = get_ssh_from_saved()
    try:
        sftp = ssh.open_sftp()
        try:
            with sftp.file(path, "r") as f:
                content = f.read().decode("utf-8", errors="replace")
            return {"content": content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Không thể đọc file: {str(e)}")
    finally:
        ssh.close()

@app.post("/api/files/content")
def api_save_file_content(
    path: str = Body(..., embed=True),
    content: str = Body(..., embed=True)
):
    ssh = get_ssh_from_saved()
    try:
        sftp = ssh.open_sftp()
        try:
            with sftp.file(path, "w") as f:
                f.write(content)
            return {"status": "success", "message": "Đã lưu nội dung file thành công!"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Không thể lưu file: {str(e)}")
    finally:
        ssh.close()

@app.post("/api/terminal")
def api_terminal(command: str = Body(..., embed=True)):
    ssh = get_ssh_from_saved()
    cfg = get_saved_config()
    password = cfg.get("password", "") if cfg else ""
    try:
        # Sử dụng get_pty=True để giả lập TTY terminal, cho phép sudo chạy
        stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
        
        # Nếu lệnh chứa sudo và có mật khẩu đã lưu, tự động truyền mật khẩu vào
        if "sudo" in command and password:
            import time
            time.sleep(0.3)
            stdin.write(password + "\n")
            stdin.flush()
            
        out = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")
        return {"output": out, "error": err}
    finally:
        ssh.close()

if __name__ == "__main__":
    import uvicorn
    # Khởi động ở port 9000
    print("-----------------------------------------------------------------")
    print("  VPS Manager Dashboard is running at: http://localhost:9000")
    print("-----------------------------------------------------------------")
    uvicorn.run("main:app", host="127.0.0.1", port=9000, reload=True)
