from benchbuild.projects.benchbuild.group import BenchBuildGroup
from os import path
from plumbum import local


class TCC(BenchBuildGroup):
    NAME = 'tcc'
    DOMAIN = 'compilation'

    src_dir = "tcc-0.9.26"
    src_file = src_dir + ".tar.bz2"
    src_uri = "http://download-mirror.savannah.gnu.org/releases/tinycc/" + \
        src_file

    def download(self):
        from benchbuild.utils.downloader import Wget
        from plumbum.cmd import tar

        with local.cwd(self.builddir):
            Wget(self.src_uri, self.src_file)
            tar("xjf", self.src_file)

    def configure(self):
        from benchbuild.utils.compiler import lt_clang
        from benchbuild.utils.run import run
        from plumbum.cmd import mkdir
        tcc_dir = path.join(self.builddir, self.src_dir)

        with local.cwd(self.builddir):
            mkdir("build")
            clang = lt_clang(self.cflags, self.ldflags,
                             self.compiler_extension)
        with local.cwd(path.join(self.builddir, "build")):
            configure = local[path.join(tcc_dir, "configure")]
            run(configure["--cc=" + str(clang), "--libdir=/usr/lib64"])

    def build(self):
        from plumbum.cmd import make
        from benchbuild.utils.run import run

        with local.cwd(path.join(self.builddir, "build")):
            run(make)

    def run_tests(self, experiment):
        from plumbum.cmd import make
        from benchbuild.project import wrap
        from benchbuild.utils.run import run

        wrap(self.run_f, experiment)
        with local.cwd(self.builddir):
            run(make["test"])
