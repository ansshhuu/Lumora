from pathlib import Path
from urllib.parse import urlparse
from git import Repo 

ALLOWED_HOSTS={"github.com","www.github.com"}

def validate_repo_url(url:str)->bool:
    
    par=urlparse(url)

    if par.scheme!="https":
        return False
    if par.netloc not in ALLOWED_HOSTS:
        return False
    path = par.path.strip("/")
    parts = path.split("/")

    if len(parts)!=2:
        return False
    owner, repo = parts
    if not owner or not repo:
        return False

    return True
def build_clone_url(url: str, token: str | None = None) -> str:

    if not token:
        return url

    return url.replace(
        "https://",
        f"https://{token}@",
        1,
    )

def clone_repo(
    url: str,
    destination: str,
    token: str | None = None,
) -> Path:

    if not validate_repo_url(url):
        raise ValueError(f"Invalid GitHub repository URL:\n{url}")

    destination = Path(destination)

    if destination.exists():
        raise FileExistsError(
            f"Destination already exists:\n{destination}"
        )

    clone_url = build_clone_url(url, token)

    Repo.clone_from(
        clone_url,
        destination,
        depth=1,
        single_branch=True,
    )

    return destination
"""
if __name__ == "__main__":

    # Public repository
    repo = clone_repo(
        url="https://github.com/psf/requests.git",
        destination="repos/requests",
    )

    print(f"Cloned to: {repo}")

    token = os.getenv("GITHUB_TOKEN")

    repo = clone_repo(
        url="https://github.com/your-org/private-repo.git",
        destination="repos/private-repo",
        token=token,
    )

    print(repo)
    """