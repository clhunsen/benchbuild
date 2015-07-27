#!/usr/bin/env python
# encoding: utf-8

""" Analyze the PPROF database. """

from plumbum import cli
from pprof.driver import PollyProfiling


def print_runs(query):
    """ Print all rows in this result query. """

    if query is None:
        return

    for tup in query:
        print("{} @ {} - {} id: {} group: {}".format(
            tup.finished,
            tup.experiment_name, tup.project_name,
            tup.experiment_group, tup.run_group))


def print_logs(query, types=None):
    """ Print status logs. """
    from pprof.utils.schema import RunLog

    if query is None:
        return

    query = query.filter(RunLog.status != 0)

    for run, log in query:
        print("{} @ {} - {} id: {} group: {} status: {}".format(
            run.finished, run.experiment_name, run.project_name,
            run.experiment_group, run.run_group,
            log.status))
        if "stderr" in types:
            print "StdErr:"
            print(log.stderr)
        if "stdout" in types:
            print "StdOut:"
            print(log.stdout)
        print


@PollyProfiling.subcommand("log")
class PprofLog(cli.Application):

    """ Frontend command to the pprof database. """

    @cli.switch(["-E", "--experiment"], str, list=True,
                help="Experiments to fetch the log for.")
    def experiment(self, experiments):
        """ Set the experiments to fetch the log for. """
        self._experiments = experiments

    @cli.switch(["-e", "--experiment-id"], str, list=True,
                help="Experiment IDs to fetch the log for.")
    def experiment_ids(self, experiment_ids):
        """ Set the experiment ids to fetch the log for. """
        self._experiment_ids = experiment_ids

    @cli.switch(["-P", "--project"], str, list=True,
                help="Projects to fetch the log for.")
    def project(self, projects):
        """ Set the projects to fetch the log for. """
        self._projects = projects

    @cli.switch(["-p", "--project-id"], str, list=True,
                help="Project IDs to fetch the log for.")
    def project_ids(self, project_ids):
        """ Set the project ids to fetch the log for. """
        self._project_ids = project_ids

    @cli.switch(["-t", "--type"], cli.Set("stdout", "stderr"), list=True,
                help="Set the output types to print.")
    def log_type(self, types):
        """ Set the output types to print. """
        self._types = types

    _experiments = None
    _experiment_ids = None
    _projects = None
    _project_ids = None
    _types = None

    def main(self):
        """ Run the log command. """
        from pprof.utils.schema import Session, Run, RunLog

        s = Session()

        exps = self._experiments
        exp_ids = self._experiment_ids
        projects = self._projects
        project_ids = self._project_ids
        types = self._types

        if types is not None:
            query = s.query(Run, RunLog).filter(Run.id == RunLog.run_id)
        else:
            query = s.query(Run)

        if exps is not None:
            query = query.filter(Run.experiment_name.in_(exps))

        if exp_ids is not None:
            query = query.filter(Run.experiment_group.in_(exp_ids))

        if projects is not None:
            query = query.filter(Run.project_name.in_(projects))

        if project_ids is not None:
            query = query.filter(Run.run_group.in_(project_ids))

        if types is not None:
            print_logs(query, types)
        else:
            print_runs(query)