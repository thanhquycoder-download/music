import base64
import os
import requests
from pathlib import Path
from typing import Optional, Tuple
from app.config import settings

class GitHubStorageService:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.owner = settings.GITHUB_OWNER
        self.repo = settings.GITHUB_REPO
        self.branch = settings.GITHUB_BRANCH
        self.api_base = f"https://api.github.com/repos/{self.owner}/{self.repo}"

    @property
    def headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MusicEcosystem-Bot"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get_jsdelivr_url(self, repo_path: str) -> str:
        """
        Chuyển đổi đường dẫn file trong repo sang URL jsDelivr CDN hỗ trợ tua (HTTP Range Requests).
        Ví dụ: audios/abc.mp3 -> https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/audios/abc.mp3
        """
        return f"https://cdn.jsdelivr.net/gh/{self.owner}/{self.repo}@{self.branch}/{repo_path}"

    def get_raw_github_url(self, repo_path: str) -> str:
        """
        Chuyển đổi đường dẫn file sang URL raw.githubusercontent.com (Fastly CDN).
        Hỗ trợ Range Requests và không bị giới hạn 20MB như jsDelivr.
        """
        return f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{repo_path}"

    def get_cdn_url(self, repo_path: str, file_size: int = 0) -> str:
        """
        Lựa chọn CDN tối ưu:
        - Audio (.mp3): Dùng raw.githubusercontent.com (Fastly CDN hỗ trợ Range Tua mượt mà, không giới hạn 20MB, không bị 403).
        - Images (.jpg, .png): Dùng jsDelivr CDN để nén và tải ảnh thumbnail nhanh.
        """
        if repo_path.lower().endswith(('.mp3', '.m4a', '.wav')) or file_size >= 19 * 1024 * 1024:
            return self.get_raw_github_url(repo_path)
        return self.get_jsdelivr_url(repo_path)

    def upload_file(self, local_file_path: Path, repo_path: str, commit_message: str) -> str:
        """
        Upload file lên GitHub Repo bằng REST API PUT /repos/{owner}/{repo}/contents/{path}.
        Sau đó trả về đường dẫn CDN tối ưu (jsDelivr hoặc raw.githubusercontent.com).
        """
        if not self.token or not self.owner or not self.repo:
            raise ValueError("Chưa cấu hình GITHUB_TOKEN, GITHUB_OWNER hoặc GITHUB_REPO trong file .env!")

        if not local_file_path.exists():
            raise FileNotFoundError(f"File cục bộ không tồn tại: {local_file_path}")

        file_size = local_file_path.stat().st_size

        # Đảm bảo file không vượt quá giới hạn 19MB của GitHub Contents REST API
        if file_size > 19 * 1024 * 1024 and str(local_file_path).lower().endswith(('.mp3', '.m4a')):
            compressed_target = local_file_path.parent / f"gh_opt_{local_file_path.name}"
            try:
                import subprocess
                subprocess.run([
                    settings.ffmpeg_binary, "-y", "-i", str(local_file_path),
                    "-vn", "-threads", "0", "-b:a", "96k", str(compressed_target)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                if compressed_target.exists() and compressed_target.stat().st_size > 0:
                    local_file_path.unlink()
                    compressed_target.rename(local_file_path)
                    file_size = local_file_path.stat().st_size
            except Exception as ce:
                print(f"[GitHubStorage] Compress fallback error: {ce}")

        # Đọc file và mã hóa sang Base64
        with open(local_file_path, "rb") as f:
            content_bytes = f.read()
            encoded_content = base64.b64encode(content_bytes).decode("utf-8")

        url = f"{self.api_base}/contents/{repo_path}"

        # Kiểm tra xem file đã tồn tại hay chưa để lấy sha (nếu cập nhật)
        get_res = requests.get(url, headers=self.headers, params={"ref": self.branch}, timeout=10)
        sha = None
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")

        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": self.branch
        }
        if sha:
            payload["sha"] = sha

        put_res = None
        try:
            put_res = requests.put(url, headers=self.headers, json=payload, timeout=45)
            if put_res.status_code in (200, 201):
                return self.get_cdn_url(repo_path, file_size)
            else:
                print(f"[GitHubStorage] GitHub API status {put_res.status_code}: {put_res.text[:200]}")
        except Exception as e:
            print(f"[GitHubStorage] GitHub API upload error: {e}")

        # Local Media Storage Fallback:
        # Nếu GitHub API hết hạn token hoặc mạng chậm, lưu ngay vào thư mục media của server
        # để đảm bảo người dùng bóc tách nhạc luôn thành công 100%, không bị báo lỗi.
        media_dir = Path(__file__).resolve().parent.parent.parent / "media"
        target_path = media_dir / repo_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(local_file_path), str(target_path))
        return f"/media/{repo_path}"

    def upload_song_assets(self, audio_file: Path, cover_file: Optional[Path], song_id: str) -> Tuple[str, Optional[str]]:
        """
        Upload file âm thanh .mp3 và ảnh thumbnail lên GitHub Storage.
        Ngay sau khi upload thành công, tự động xóa file tạm trên server để tiết kiệm dung lượng.
        """
        audio_repo_path = f"audios/{song_id}.mp3"
        audio_cdn_url = self.upload_file(
            local_file_path=audio_file,
            repo_path=audio_repo_path,
            commit_message=f"feat(audio): add song {song_id}.mp3"
        )

        cover_cdn_url = None
        if cover_file and cover_file.exists():
            cover_ext = cover_file.suffix or ".jpg"
            cover_repo_path = f"covers/{song_id}{cover_ext}"
            cover_cdn_url = self.upload_file(
                local_file_path=cover_file,
                repo_path=cover_repo_path,
                commit_message=f"feat(cover): add cover for {song_id}"
            )

        # XÓA FILE TẠM NGAY LẬP TỨC ĐỂ SERVER LUÔN DƯỚI 1GB
        self.cleanup_temp_files([audio_file, cover_file])

        return audio_cdn_url, cover_cdn_url

    @staticmethod
    def cleanup_temp_files(files: list):
        """Dọn sạch các file tạm trên server."""
        for f in files:
            if f and isinstance(f, (str, Path)):
                path_obj = Path(f)
                try:
                    if path_obj.exists():
                        path_obj.unlink()
                except Exception as e:
                    print(f"[Cleanup] Không thể xóa file tạm {path_obj}: {e}")

github_storage = GitHubStorageService()

