"""Unit tests for repo URL validation and clone URL building.

Nothing here touches the network or git: clone_repo is only exercised through
its guard clauses, which reject before Repo.clone_from would ever be called.
"""

import pytest

from lumora.ingestion.clone import (
    ALLOWED_HOSTS,
    build_clone_url,
    clone_repo,
    validate_repo_url,
)


# --- valid URLs -----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/psf/requests",
        "https://github.com/psf/requests.git",
        "https://www.github.com/psf/requests",
        "https://github.com/psf/requests/",
        "https://github.com/Anshu-Panwar/lumora",
        "https://github.com/owner-with-dash/repo_with_underscore",
        "https://github.com/a/b",
    ],
)
def test_valid_github_urls_pass(url):
    assert validate_repo_url(url) is True


@pytest.mark.parametrize("host", sorted(ALLOWED_HOSTS))
def test_every_allowed_host_passes(host):
    assert validate_repo_url(f"https://{host}/owner/repo") is True


# --- rejected hosts -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/owner/repo",
        "https://bitbucket.org/owner/repo",
        "https://evil.com/owner/repo",
        "https://notgithub.com/owner/repo",
        "https://example.com/github.com/owner/repo",
    ],
)
def test_non_github_hosts_are_rejected(url):
    assert validate_repo_url(url) is False


def test_lookalike_subdomain_host_is_rejected():
    """github.com.evil.com must not pass as GitHub."""
    assert validate_repo_url("https://github.com.evil.com/owner/repo") is False


def test_userinfo_host_spoof_is_rejected():
    """`github.com@evil.com` puts github.com in userinfo, not the host."""
    assert validate_repo_url("https://github.com@evil.com/owner/repo") is False


# --- rejected schemes -----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",
        "git://github.com/owner/repo",
        "ssh://git@github.com/owner/repo",
        "file:///etc/passwd",
        "ftp://github.com/owner/repo",
        "git@github.com:owner/repo.git",
    ],
)
def test_non_https_schemes_are_rejected(url):
    assert validate_repo_url(url) is False


# --- malformed paths ------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/",
        "https://github.com",
        "https://github.com/owner",
        "https://github.com/owner/repo/extra",
        "https://github.com/owner/repo/tree/main",
        "https://github.com//repo",
        "https://github.com/owner/",
    ],
)
def test_malformed_paths_are_rejected(url):
    assert validate_repo_url(url) is False


@pytest.mark.parametrize("url", ["", "   ", "not a url", "javascript:alert(1)"])
def test_garbage_input_is_rejected(url):
    assert validate_repo_url(url) is False


# --- clone URL building ---------------------------------------------------------


def test_build_clone_url_without_token_is_unchanged():
    url = "https://github.com/owner/repo.git"

    assert build_clone_url(url) == url
    assert build_clone_url(url, None) == url


def test_build_clone_url_injects_token_into_host():
    result = build_clone_url("https://github.com/owner/repo.git", "ghp_secret")

    assert result == "https://ghp_secret@github.com/owner/repo.git"


def test_build_clone_url_only_replaces_the_first_scheme_occurrence():
    """A repo name containing the scheme text must not get a second token."""
    result = build_clone_url("https://github.com/owner/https://x", "tok")

    assert result.count("tok@") == 1
    assert result.startswith("https://tok@github.com/")


def test_build_clone_url_treats_empty_token_as_no_token():
    url = "https://github.com/owner/repo.git"

    assert build_clone_url(url, "") == url


# --- clone_repo guard clauses (no network) --------------------------------------


def test_clone_repo_rejects_invalid_url_before_cloning(tmp_path):
    with pytest.raises(ValueError, match="Invalid GitHub repository URL"):
        clone_repo("https://evil.com/owner/repo", str(tmp_path / "dest"))


def test_clone_repo_rejects_existing_destination(tmp_path):
    dest = tmp_path / "existing"
    dest.mkdir()

    with pytest.raises(FileExistsError):
        clone_repo("https://github.com/owner/repo", str(dest))


def test_clone_repo_validates_url_before_checking_destination(tmp_path):
    """Ordering matters: a bad URL is a ValueError even if dest also exists."""
    dest = tmp_path / "existing"
    dest.mkdir()

    with pytest.raises(ValueError):
        clone_repo("http://github.com/owner/repo", str(dest))
