from app.version import git_revision


def test_git_revision_returns_string():
    rev = git_revision()
    assert isinstance(rev, str)
    assert rev
