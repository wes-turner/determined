import uuid
from typing import Callable, Optional, Sequence, TypeVar

import pytest

from determined.common import api
from determined.common.api import authentication, bindings, certs, errors
from tests import config as conf


def get_random_string() -> str:
    return str(uuid.uuid4())


def determined_test_session(
    credentials: Optional[authentication.Credentials] = None,
    admin: Optional[bool] = None,
) -> api.Session:
    assert admin is None or credentials is None, "admin and credentials are mutually exclusive"

    if credentials is None:
        if admin:
            credentials = conf.ADMIN_CREDENTIALS
        else:
            credentials = authentication.Credentials("determined", "")

    murl = conf.make_master_url()
    certs.cli_cert = certs.default_load(murl)
    authentication.cli_auth = authentication.Authentication(
        murl, requested_user=credentials.username, password=credentials.password
    )
    return api.Session(murl, credentials.username, authentication.cli_auth, certs.cli_cert)


def create_test_user(
    add_password: bool = False,
    session: Optional[api.Session] = None,
    user: Optional[bindings.v1User] = None,
) -> authentication.Credentials:
    session = session or determined_test_session(admin=True)
    user = user or bindings.v1User(username=get_random_string(), admin=False, active=True)
    password = get_random_string() if add_password else ""
    bindings.post_PostUser(session, body=bindings.v1PostUserRequest(user=user, password=password))
    return authentication.Credentials(user.username, password)


def configure_token_store(credentials: authentication.Credentials) -> None:
    """Authenticate the user for CLI usage with the given credentials."""
    token_store = authentication.TokenStore(conf.make_master_url())
    certs.cli_cert = certs.default_load(conf.make_master_url())
    token = authentication.do_login(
        conf.make_master_url(), credentials.username, credentials.password, certs.cli_cert
    )
    token_store.set_token(credentials.username, token)
    token_store.set_active(credentials.username)


def launch_ntsc(
    session: api.Session,
    workspace_id: int,
    typ: api.NTSC_Kind,
    exp_id: Optional[int] = None,
    template: Optional[str] = None,
) -> api.AnyNTSC:
    if typ == api.NTSC_Kind.notebook:
        return bindings.post_LaunchNotebook(
            session,
            body=bindings.v1LaunchNotebookRequest(workspaceId=workspace_id, templateName=template),
        ).notebook
    elif typ == api.NTSC_Kind.tensorboard:
        experiment_ids = [exp_id] if exp_id else []
        return bindings.post_LaunchTensorboard(
            session,
            body=bindings.v1LaunchTensorboardRequest(
                workspaceId=workspace_id, experimentIds=experiment_ids, templateName=template
            ),
        ).tensorboard
    elif typ == api.NTSC_Kind.shell:
        return bindings.post_LaunchShell(
            session,
            body=bindings.v1LaunchShellRequest(workspaceId=workspace_id, templateName=template),
        ).shell
    elif typ == api.NTSC_Kind.command:
        return bindings.post_LaunchCommand(
            session,
            body=bindings.v1LaunchCommandRequest(
                workspaceId=workspace_id,
                config={
                    "entrypoint": ["sleep", "100"],
                },
                templateName=template,
            ),
        ).command
    else:
        raise ValueError("unknown type")


def kill_ntsc(session: api.Session, typ: api.NTSC_Kind, ntsc_id: str) -> None:
    if typ == api.NTSC_Kind.notebook:
        bindings.post_KillNotebook(session, notebookId=ntsc_id)
    elif typ == api.NTSC_Kind.tensorboard:
        bindings.post_KillTensorboard(session, tensorboardId=ntsc_id)
    elif typ == api.NTSC_Kind.shell:
        bindings.post_KillShell(session, shellId=ntsc_id)
    elif typ == api.NTSC_Kind.command:
        bindings.post_KillCommand(session, commandId=ntsc_id)
    else:
        raise ValueError("unknown type")


def set_prio_ntsc(session: api.Session, typ: api.NTSC_Kind, ntsc_id: str, prio: int) -> None:
    if typ == api.NTSC_Kind.notebook:
        bindings.post_SetNotebookPriority(
            session, notebookId=ntsc_id, body=bindings.v1SetNotebookPriorityRequest(priority=prio)
        )
    elif typ == api.NTSC_Kind.tensorboard:
        bindings.post_SetTensorboardPriority(
            session,
            tensorboardId=ntsc_id,
            body=bindings.v1SetTensorboardPriorityRequest(priority=prio),
        )
    elif typ == api.NTSC_Kind.shell:
        bindings.post_SetShellPriority(
            session, shellId=ntsc_id, body=bindings.v1SetShellPriorityRequest(priority=prio)
        )
    elif typ == api.NTSC_Kind.command:
        bindings.post_SetCommandPriority(
            session, commandId=ntsc_id, body=bindings.v1SetCommandPriorityRequest(priority=prio)
        )
    else:
        raise ValueError("unknown type")


def list_ntsc(
    session: api.Session, typ: api.NTSC_Kind, workspace_id: Optional[int] = None
) -> Sequence[api.AnyNTSC]:
    if typ == api.NTSC_Kind.notebook:
        return bindings.get_GetNotebooks(session, workspaceId=workspace_id).notebooks
    elif typ == api.NTSC_Kind.tensorboard:
        return bindings.get_GetTensorboards(session, workspaceId=workspace_id).tensorboards
    elif typ == api.NTSC_Kind.shell:
        return bindings.get_GetShells(session, workspaceId=workspace_id).shells
    elif typ == api.NTSC_Kind.command:
        return bindings.get_GetCommands(session, workspaceId=workspace_id).commands
    else:
        raise ValueError("unknown type")


_scheduler_type: Optional[bindings.v1SchedulerType] = None


# Queries the determined master for resource pool information to determine if agent is used
# Currently we are assuming that all resource pools are of the same scheduler type
# which is why only the first resource pool's type is checked.
def _get_scheduler_type() -> Optional[bindings.v1SchedulerType]:
    global _scheduler_type
    if _scheduler_type is None:
        try:
            sess = determined_test_session()
            resourcePool = bindings.get_GetResourcePools(sess).resourcePools
            if not resourcePool:
                raise ValueError(
                    "Resource Pool returned no value. Make sure the resource pool is set."
                )
            _scheduler_type = resourcePool[0].schedulerType
        except (errors.APIException, errors.MasterNotFoundException):
            pass
    return _scheduler_type


F = TypeVar("F", bound=Callable)


def skipif_not_hpc(reason: str = "test is hpc-specific") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        st = _get_scheduler_type()
        if st is None:
            return f
        if st not in (bindings.v1SchedulerType.SLURM, bindings.v1SchedulerType.PBS):
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator


def skipif_not_slurm(reason: str = "test is slurm-specific") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        st = _get_scheduler_type()
        if st is None:
            return f
        if st != bindings.v1SchedulerType.SLURM:
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator


def skipif_not_pbs(reason: str = "test is slurm-specific") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        st = _get_scheduler_type()
        if st is None:
            return f
        if st != bindings.v1SchedulerType.PBS:
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator


def is_hpc() -> bool:
    st = _get_scheduler_type()
    if st is None:
        raise RuntimeError("unable to contact master to determine is_hpc()")
    return st in (bindings.v1SchedulerType.SLURM, bindings.v1SchedulerType.PBS)


_is_ee: Optional[bool] = None


def _get_ee() -> Optional[bool]:
    global _is_ee

    if _is_ee is None:
        try:
            info = api.get(conf.make_master_url(), "info", authenticated=False).json()
            _is_ee = "sso_providers" in info
        except (errors.APIException, errors.MasterNotFoundException):
            pass

    return _is_ee


def skipif_ee(reason: str = "test is oss-specific") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        ee = _get_ee()
        if ee is None:
            return f
        if ee:
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator


def skipif_not_ee(reason: str = "test is ee-specific") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        ee = _get_ee()
        if ee is None:
            return f
        if not ee:
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator


_scim_enabled: Optional[bool] = None


def _get_scim_enabled() -> Optional[bool]:
    global _scim_enabled

    if _scim_enabled is None:
        try:
            info = api.get(conf.make_master_url(), "info", authenticated=False).json()
            _scim_enabled = bool(info.get("sso_providers") and len(info["sso_providers"]) > 0)
        except (errors.APIException, errors.MasterNotFoundException):
            pass

    return _scim_enabled


def skipif_scim_not_enabled(reason: str = "scim is required for this test") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        se = _get_scim_enabled()
        if se is None:
            return f
        if not se:
            return pytest.mark.skipif(True, reason=reason)(f)  # type: ignore
        return f

    return decorator
