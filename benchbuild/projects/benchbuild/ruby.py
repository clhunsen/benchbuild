from benchbuild.settings import CFG
from benchbuild.projects.benchbuild.group import BenchBuildGroup
from os import path
from plumbum import local


class Ruby(BenchBuildGroup):
    NAME = 'ruby'
    DOMAIN = 'compilation'

    src_dir = "ruby-2.2.2"
    src_file = src_dir + ".tar.gz"
    src_uri = "http://cache.ruby-lang.org/pub/ruby/2.2/" + src_file

    def download(self):
        from benchbuild.utils.downloader import Wget
        from plumbum.cmd import tar

        with local.cwd(self.builddir):
            Wget(self.src_uri, self.src_file)
            tar("xfz", self.src_file)

    def configure(self):
        from benchbuild.utils.compiler import lt_clang, lt_clang_cxx
        from benchbuild.utils.run import run

        ruby_dir = path.join(self.builddir, self.src_dir)
        clang = lt_clang(self.cflags, self.ldflags, self.compiler_extension)
        clang_cxx = lt_clang_cxx(self.cflags, self.ldflags,
                                 self.compiler_extension)
        with local.cwd(ruby_dir):
            with local.env(CC=str(clang), CXX=str(clang_cxx)):
                configure = local["./configure"]
                run(configure["--with-static-linked-ext", "--disable-shared"])

    def build(self):
        from plumbum.cmd import make
        from benchbuild.utils.run import run

        ruby_dir = path.join(self.builddir, self.src_dir)
        with local.cwd(ruby_dir):
            run(make["-j", CFG["jobs"]])

    def run_tests(self, experiment):
        from plumbum.cmd import ruby
        from benchbuild.project import wrap
        from benchbuild.utils.run import run

        ruby_dir = path.join(self.builddir, self.src_dir)
        exp = wrap(path.join(ruby_dir, "ruby"), experiment)

        with local.env(RUBYOPT=""):
            run(ruby[path.join(self.testdir, "benchmark", "run.rb"),
                     "--ruby=\"" + str(exp) + "\"", "--opts=\"-I" + path.join(
                         self.testdir, "lib") + " -I" + path.join(
                             self.testdir, ".") + " -I" + path.join(
                                 self.testdir, ".ext", "common") + "\"", "-r"])
