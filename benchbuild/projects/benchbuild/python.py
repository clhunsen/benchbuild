from benchbuild.projects.benchbuild.group import BenchBuildGroup
from os import path
from plumbum import local
from plumbum.cmd import find


class Python(BenchBuildGroup):
    """ python benchmarks """

    NAME = 'python'
    DOMAIN = 'compilation'

    src_dir = "Python-3.4.3"
    src_file = src_dir + ".tar.xz"
    src_uri = "https://www.python.org/ftp/python/3.4.3/" + src_file

    def download(self):
        from benchbuild.utils.downloader import Wget
        from plumbum.cmd import tar

        with local.cwd(self.builddir):
            Wget(self.src_uri, self.src_file)
            tar("xfJ", self.src_file)

    def configure(self):
        from benchbuild.utils.compiler import lt_clang, lt_clang_cxx
        from benchbuild.utils.run import run
        python_dir = path.join(self.builddir, self.src_dir)

        with local.cwd(self.builddir):
            clang = lt_clang(self.cflags, self.ldflags,
                             self.compiler_extension)
            clang_cxx = lt_clang_cxx(self.cflags, self.ldflags,
                                     self.compiler_extension)

        with local.cwd(python_dir):
            configure = local["./configure"]
            with local.env(CC=str(clang), CXX=str(clang_cxx)):
                run(configure["--disable-shared", "--without-gcc"])

    def build(self):
        from plumbum.cmd import make
        from benchbuild.utils.run import run
        python_dir = path.join(self.builddir, self.src_dir)
        with local.cwd(python_dir):
            run(make)

    def run_tests(self, experiment):
        from plumbum.cmd import make
        from benchbuild.project import wrap
        from benchbuild.utils.run import run

        python_dir = path.join(self.builddir, self.src_dir)
        exp = wrap(path.join(python_dir, "python"), experiment)

        with local.cwd(python_dir):
            run(make["TESTPYTHON=" + str(exp), "-i", "test"])
