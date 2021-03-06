"""
The 'raw' Experiment.

This experiment is the basic experiment in the benchbuild study. It simply runs
all projects after compiling it with -O3. The binaries are wrapped
with the time command and results are written to the database.

This forms the baseline numbers for the other experiments.

Measurements
------------

3 Metrics are generated during this experiment:
    time.user_s - The time spent in user space in seconds (aka virtual time)
    time.system_s - The time spent in kernel space in seconds (aka system time)
    time.real_s - The time spent overall in seconds (aka Wall clock)
"""

from benchbuild.experiment import RuntimeExperiment
from benchbuild.utils.actions import (Prepare, Build, Download, Configure, Clean,
                                 MakeBuildDir, Run, Echo)
from benchbuild.utils.run import guarded_exec, handle_stdin, fetch_time_output
from benchbuild.utils.db import persist_time, persist_config
from plumbum.cmd import time

from benchbuild.settings import CFG
from benchbuild.utils.run import partial
from plumbum import local


def run_with_time(project, experiment, config, jobs, run_f, args, **kwargs):
    """
    Run the given binary wrapped with time.

    Args:
        project: The benchbuild project that has called us.
        experiment: The benchbuild experiment which we operate under.
        config: The benchbuild configuration we are running with.
        jobs: The number of cores we are allowed to use. This may differ
            from the actual amount of available cores, obey it.
            We should enforce this from the outside. However, at the moment we
            do not do this.
        run_f: The file we want to execute.
        args: List of arguments that should be passed to the wrapped binary.
        **kwargs: Dictionary with our keyword args. We support the following
            entries:

            project_name: The real name of our project. This might not
                be the same as the configured project name, if we got wrapped
                with ::benchbuild.project.wrap_dynamic
            has_stdin: Signals whether we should take care of stdin.
    """
    CFG.update(config)
    project.name = kwargs.get("project_name", project.name)
    timing_tag = "BB-TIME: "

    run_cmd = time["-f", timing_tag + "%U-%S-%e", run_f]
    run_cmd = handle_stdin(run_cmd[args], kwargs)

    with local.env(OMP_NUM_THREADS=str(jobs)):
        with guarded_exec(run_cmd, project, experiment) as run:
            ri = run()
        timings = fetch_time_output(
            timing_tag, timing_tag + "{:g}-{:g}-{:g}", ri.stderr.split("\n"))
        if not timings:
            return

    persist_time(ri.db_run, ri.session, timings)
    persist_config(ri.db_run, ri.session, {"cores": str(jobs)})


class RawRuntime(RuntimeExperiment):
    """The polyjit experiment."""

    NAME = "raw"

    def actions_for_project(self, project):
        """Compile & Run the experiment with -O3 enabled."""
        project.cflags = ["-O3", "-fno-omit-frame-pointer"]
        project.runtime_extension = \
            partial(run_with_time, project, self, CFG, CFG["jobs"].value())
        actns = [
            MakeBuildDir(project),
            Echo("Compiling... {}".format(project.name)),
            Prepare(project),
            Download(project),
            Configure(project),
            Build(project),
            Echo("Running... {}".format(project.name)),
            Run(project),
            Clean(project),
        ]
        return actns
