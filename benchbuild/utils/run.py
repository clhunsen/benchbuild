"""
Experiment helpers
"""
import os
from plumbum.cmd import mkdir  # pylint: disable=E0401
from contextlib import contextmanager
from types import SimpleNamespace


def partial(func, *args, **kwargs):
    """
    Partial function application.

    This performs standard partial application on the given function. However,
    we do not check if parameter values in args and kwargs collide with each
    other.

    Args:
        func: The original function.
        *args: Positional arguments that should be applied partially.
        **kwargs: Keyword arguments that should be applied partially.

    Returns:
        A new function that has all given args and kwargs bound.
    """
    frozen_args = args
    frozen_kwargs = kwargs

    def partial_func(*args, **kwargs):
        """ The partial function with pre-bound arguments. """
        nonlocal frozen_args
        nonlocal frozen_kwargs
        nonlocal func
        thawed_args = frozen_args + args
        thawed_kwargs = frozen_kwargs.copy()
        thawed_kwargs.update(kwargs)
        func(*thawed_args, **thawed_kwargs)

    return partial_func


def handle_stdin(cmd, kwargs):
    """
    Handle stdin for wrapped runtime executors.

    This little helper checks the kwargs for a `has_stdin` key containing
    a boolean value. If necessary it will pipe in the stdin of this process
    into the plumbum command.

    Args:
        cmd (plumbum.cmd): Command to wrap a stdin handler around.
        kwargs: Dictionary containing the kwargs.
            We check for they key `has_stdin`

    Returns:
        A new plumbum command that deals with stdin redirection, if needed.
    """
    assert isinstance(kwargs, dict)
    import sys

    has_stdin = kwargs.get("has_stdin", False)
    if has_stdin:
        run_cmd = (cmd < sys.stdin)
    else:
        run_cmd = cmd

    return run_cmd


def fetch_time_output(marker, format_s, ins):
    """
    Fetch the output /usr/bin/time from a.

    Args:
        marker: The marker that limits the time output
        format_s: The format string used to parse the timings
        ins: A list of lines we look for the output.

    Returns:
        A list of timing tuples
    """
    from parse import parse

    timings = [x for x in ins if marker in x]
    res = [parse(format_s, t) for t in timings]
    return [_f for _f in res if _f]


class GuardedRunException(Exception):
    """
    BB Run exception.

    Contains an exception that ocurred during execution of a benchbuild
    experiment.
    """

    def __init__(self, what, db_run, session):
        """
        Exception raised when a binary failed to execute properly.

        Args:
            what: the original exception.
            run: the run during which we encountered ``what``.
            session: the db session we want to log to.
        """
        super(GuardedRunException, self).__init__()

        self.what = what
        self.run = db_run

        if isinstance(what, KeyboardInterrupt):
            session.rollback()

    def __str__(self):
        return self.what.__str__()

    def __repr__(self):
        return self.what.__repr__()


def begin_run_group(project):
    """
    Begin a run_group in the database.

    A run_group groups a set of runs for a given project. This models a series
    of runs that form a complete binary runtime test.

    Args:
        project: The project we begin a new run_group for.

    Returns:
        ``(group, session)`` where group is the created group in the
        database and session is the database session this group lives in.
    """
    from benchbuild.utils.db import create_run_group
    from datetime import datetime

    group, session = create_run_group(project)
    group.begin = datetime.now()
    group.status = 'running'

    session.commit()
    return group, session


def end_run_group(group, session):
    """
    End the run_group successfully.

    Args:
        group: The run_group we want to complete.
        session: The database transaction we will finish.
    """
    from datetime import datetime

    group.end = datetime.now()
    group.status = 'completed'
    session.commit()


def fail_run_group(group, session):
    """
    End the run_group unsuccessfully.

    Args:
        group: The run_group we want to complete.
        session: The database transaction we will finish.
    """
    from datetime import datetime

    group.end = datetime.now()
    group.status = 'failed'
    session.commit()


def begin(command, pname, ename, group):
    """
    Begin a run in the database log.

    Args:
        command: The command that will be executed.
        pname: The project name we belong to.
        ename: The experiment name we belong to.
        group: The run group we belong to.

    Returns:
        (run, session), where run is the generated run instance and session the
        associated transaction for later use.
    """
    from benchbuild.utils.db import create_run
    from benchbuild.utils import schema as s
    from benchbuild.settings import CFG
    from datetime import datetime

    db_run, session = create_run(command, pname, ename, group)
    db_run.begin = datetime.now()
    db_run.status = 'running'
    log = s.RunLog()
    log.run_id = db_run.id
    log.begin = datetime.now()
    log.config = repr(CFG)

    session.add(log)
    session.commit()

    return db_run, session


def end(db_run, session, stdout, stderr):
    """
    End a run in the database log (Successfully).

    This will persist the log information in the database and commit the
    transaction.

    Args:
        db_run: The ``run`` schema object we belong to
        session: The db transaction we belong to.
        stdout: The stdout we captured of the run.
        stderr: The stderr we capture of the run.
    """
    from benchbuild.utils.schema import RunLog
    from datetime import datetime
    log = session.query(RunLog).filter(RunLog.run_id == db_run.id).one()
    log.stderr = stderr
    log.stdout = stdout
    log.status = 0
    log.end = datetime.now()
    db_run.end = datetime.now()
    db_run.status = 'completed'
    session.add(log)
    session.commit()


def fail(db_run, session, retcode, stdout, stderr):
    """
    End a run in the database log (Unsuccessfully).

    This will persist the log information in the database and commit the
    transaction.

    Args:
        db_run: The ``run`` schema object we belong to
        session: The db transaction we belong to.
        retcode: The return code we captured of the run.
        stdout: The stdout we captured of the run.
        stderr: The stderr we capture of the run.
    """
    from benchbuild.utils.schema import RunLog
    from datetime import datetime
    log = session.query(RunLog).filter(RunLog.run_id == db_run.id).one()
    log.stderr = stderr
    log.stdout = stdout
    log.status = retcode
    log.end = datetime.now()
    db_run.end = datetime.now()
    db_run.status = 'failed'
    session.add(log)
    session.commit()


@contextmanager
def guarded_exec(cmd, project, experiment):
    """
    Guard the execution of the given command.

    Args:
        cmd: the command we guard.
        pname: the database run we run under.
        ename: the database session this run belongs to.
        run_group: the run group this execution will belong to.

    Raises:
        RunException: If the ``cmd`` encounters an error we wrap the exception
            in a RunException and re-raise. This ends the run unsuccessfully.
    """
    from plumbum.commands import ProcessExecutionError
    from plumbum import local
    from plumbum.commands.modifiers import TEE
    from warnings import warn

    db_run, session = begin(cmd, project.name, experiment.name,
                            project.run_uuid)
    ex = None
    with local.env(BB_DB_RUN_ID=db_run.id):
        def runner(retcode=0, *args):
            retcode, stdout, stderr = cmd[args] & TEE(retcode=retcode)
            end(db_run, session, stdout, stderr)
            r = SimpleNamespace()
            r.retcode = retcode
            r.stdout = stdout
            r.stderr = stderr
            r.session = session
            r.db_run = db_run
            return r
        try:
            yield runner
        except KeyboardInterrupt:
            fail(db_run, session, -1, "", "KeyboardInterrupt")
            warn("Interrupted by user input")
            raise
        except ProcessExecutionError as proc_ex:
            fail(db_run, session,
                 proc_ex.retcode, proc_ex.stdout, proc_ex.stderr)
            raise
        except Exception as e:
            fail(db_run, session, -1, "", str(ex))
            raise


def run(command, retcode=0):
    """
    Execute a plumbum command, depending on the user's settings.

    Args:
        command: The plumbumb command to execute.
    """
    from logging import debug, info, error
    from plumbum.commands.modifiers import TEE
    info(str(command))
    command & TEE(retcode)

def uchroot_no_args():
    from benchbuild.settings import CFG
    from plumbum import local

    """Return the uchroot command without any customizations."""
    return local[CFG["uchroot"]["path"].value()]

def uchroot_no_llvm(*args, **kwargs):
    """
    Returns a uchroot command which can be called with other args to be
            executed in the uchroot.
    Args:
        args: List of additional arguments for uchroot (typical: mounts)
    Return:
        chroot_cmd
    """
    uid = kwargs.pop('uid', 0)
    gid = kwargs.pop('gid', 0)

    uchroot_cmd = uchroot_no_args()
    uchroot_cmd = uchroot_cmd["-C", "-w", "/", "-r", os.path.abspath(".")]
    uchroot_cmd = uchroot_cmd["-u", str(uid), "-g", str(gid), "-E", "-A"]
    return uchroot_cmd[args]

def uchroot(*args, **kwargs):
    """
    Returns a uchroot command which can be called with other args to be
            executed in the uchroot.
    Args:
        args: List of additional arguments for uchroot (typical: mounts)
    Return:
        chroot_cmd
    """
    from benchbuild.settings import CFG
    mkdir("-p", "llvm")
    uchroot_cmd = uchroot_no_llvm(args, kwargs)
    uchroot_cmd = uchroot_cmd["-m", str(CFG["llvm"]["dir"]) + ":llvm"]
    uchroot_cmd = uchroot_cmd.setenv(LD_LIBRARY_PATH="/llvm/lib")
    return uchroot_cmd["--"]
