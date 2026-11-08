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

        # Đọc file và mã hóa sang Base64
        with open(local_file_path, "rb") as f:
            content_bytes = f.read()
            encoded_content = base64.b64encode(content_bytes).decode("utf-8")

        url = f"{self.api_base}/contents/{repo_path}"

        # Kiểm tra xem file đã tồn tại hay chưa để lấy sha (nếu cập nhật)
        get_res = requests.get(url, headers=self.headers, params={"ref": self.branch})
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

        put_res = requests.put(url, headers=self.headers, json=payload, timeout=180)
        
        if put_res.status_code not in (200, 201):
            error_detail = put_res.text
            raise RuntimeError(f"Lỗi tải lên GitHub API ({put_res.status_code}): {error_detail}")

        return self.get_cdn_url(repo_path, file_size)

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

