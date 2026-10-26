"""Reed, 2026-10-26: the live test's "QA Owner" account goes, on the next deploy
(app.seed refresh). Only an owner named exactly that; nobody else is touched."""

from app.models.accounts import LoginSession, Role, User
from app.models.jobs import Job
from app.seed import remove_qa_owner


def _person(db, name, role, email):
    reed = db.query(User).filter_by(email="reed@example.com").one()
    user = User(workspace_id=reed.workspace_id, email=email, name=name, password_hash="x",
                role=role)  # fmt: skip
    db.add(user)
    db.commit()
    return user


def test_the_qa_owner_is_removed_once_and_nobody_else(owner, db):
    qa = _person(db, "QA Owner", Role.owner, "qa-owner@example.com")
    editor = _person(db, "QA Owner", Role.editor, "qa-editor@example.com")  # not an owner
    near = _person(db, "QA Owner 2", Role.owner, "near@example.com")  # not the exact name
    db.add(LoginSession(token_hash="t" * 64, user_id=qa.id, expires_at=qa.created_at))
    db.commit()
    assert remove_qa_owner(db) is True
    db.expire_all()
    assert db.get(User, qa.id) is None  # nothing of its own: deleted, sessions too
    assert not db.query(LoginSession).filter_by(user_id=qa.id).count()
    assert all(db.get(User, u.id).active for u in (editor, near))
    assert db.query(User).filter_by(email="reed@example.com").one().active
    assert remove_qa_owner(db) is False  # nothing left to do: says nothing


def test_a_qa_owner_with_work_is_removed_but_its_work_stays(owner, db):
    qa = _person(db, "QA Owner", Role.owner, "qa-owner@example.com")
    job = Job(workspace_id=qa.workspace_id, created_by_id=qa.id, kind="image",
              provider="fake", input={}, status="succeeded")  # fmt: skip
    db.add(job)
    db.commit()
    assert remove_qa_owner(db) is True
    db.expire_all()
    assert db.get(User, qa.id).active is False  # can't sign in; its history keeps its name
    assert db.get(Job, job.id).created_by_id == qa.id
    assert remove_qa_owner(db) is False
