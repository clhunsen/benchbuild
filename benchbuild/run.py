#!/usr/bin/env python3
"""
benchbuild's run command.

This subcommand executes experiments on a set of user-controlled projects.
See the output of benchbuild run --help for more information.
"""
import os
import sys
from plumbum import cli
from plumbum.cmd import mkdir  # pylint: disable=E0401
from benchbuild.settings import CFG
from benchbuild.utils.actions import Experiment
from benchbuild.utils import user_interface as ui
from benchbuild import experiments
from benchbuild import experiment


class BenchBuildRun(cli.Application):
    """Frontend for running experiments in the benchbuild study framework."""

    _experiment_names = []
    _project_names = []
    _list = False
    _list_experiments = False
    _group_name = None

    @cli.switch(["-E", "--experiment"],
                str,
                list=True,
                help="Specify experiments to run")
    def experiments(self, experiments):
        self._experiment_names = experiments

    @cli.switch(["-D", "--description"],
                str,
                help="A description for this experiment run")
    def experiment_tag(self, description):
        CFG["experiment_description"] = description

    @cli.switch(["-P", "--project"],
                str,
                list=True,
                requires=["--experiment"],
                help="Specify projects to run")
    def projects(self, projects):
        self._project_names = projects

    @cli.switch(["-L", "--list-experiments"], help="List available experiments")
    def list_experiments(self):
        self._list_experiments = True

    @cli.switch(["-l", "--list"],
                requires=["--experiment"],
                help="List available projects for experiment")
    def list_projects(self):
        self._list = True

    show_config = cli.Flag(["-d", "--dump-config"],
                           help="Just dump benchbuild's config and exit.",
                           default=False)

    store_config = cli.Flag(["-s", "--save-config"],
                           help="Save benchbuild's configuration.",
                           default=False)

    @cli.switch(["-G", "--group"],
                str,
                requires=["--experiment"],
                help="Run a group of projects under the given experiments")
    def group(self, group):
        self._group_name = group

    pretend = cli.Flag(['p', 'pretend'], default = False)

    def main(self):
        """Main entry point of benchbuild run."""
        project_names = self._project_names
        group_name = self._group_name

        experiments.discover()

        registry = experiment.ExperimentRegistry
        exps = registry.experiments

        if self._list_experiments:
            for exp_name in registry.experiments:
                exp_cls = exps[exp_name]
                print(exp_cls.NAME)
                docstring = exp_cls.__doc__ or "-- no docstring --"
                print(("    " + docstring))
            exit(0)

        if self._list:
            for exp_name in self._experiment_names:
                exp_cls = exps[exp_name]
                exp = exp_cls(self._project_names, self._group_name)
                print_projects(exp)
            exit(0)

        if self.show_config:
            print(repr(CFG))
            exit(0)

        if self.store_config:
            config_path = ".benchbuild.json"
            CFG.store(config_path)
            print("Storing config in {0}".format(os.path.abspath(config_path)))
            exit(0)

        if self._project_names:
            builddir = os.path.abspath(str(CFG["build_dir"]))
            if not os.path.exists(builddir):
                response = True
                if sys.stdin.isatty():
                    response = ui.query_yes_no(
                        "The build directory {dirname} does not exist yet."
                        "Should I create it?".format(dirname=builddir), "no")

                if response:
                    mkdir("-p", builddir)
                    print("Created directory {0}.".format(builddir))

        actns = []
        for exp_name in self._experiment_names:
            if exp_name in exps:
                exp_cls = exps[exp_name]
                exp = exp_cls(project_names, group_name)
                eactn = Experiment(exp, exp.actions())
                actns.append(eactn)
            else:
                from logging import error
                error("Could not find {} in the experiment registry.",
                      exp_name)

        num_actions = sum([len(x) for x in actns])
        print("Number of actions to execute: {}".format(num_actions))
        for a in actns:
            print(a)
        print()

        if not self.pretend:
            for a in actns:
                a()


def print_projects(exp):
    """
    Print a list of projects registered for that experiment.

    Args:
        exp: The experiment to print all projects for.

    """
    grouped_by = {}
    projects = exp.projects
    for name in projects:
        prj = projects[name]

        if prj.group_name not in grouped_by:
            grouped_by[prj.group_name] = []

        grouped_by[prj.group_name].append(name)

    for name in grouped_by:
        from textwrap import wrap
        print(">> {0}".format(name))
        projects = sorted(grouped_by[name])
        project_paragraph = ""
        for prj in projects:
            project_paragraph += ", {0}".format(prj)
        print("\n".join(wrap(project_paragraph[2:],
                             80,
                             break_on_hyphens=False,
                             break_long_words=False)))
        print()
