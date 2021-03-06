from benchbuild.projects.benchbuild.group import BenchBuildGroup
from os import path
from plumbum import local
from plumbum.cmd import ln


class Ccrypt(BenchBuildGroup):
    """ ccrypt benchmark """

    NAME = 'ccrypt'
    DOMAIN = 'encryption'

    check_f = "check"

    def prepare(self):
        super(Ccrypt, self).prepare()
        check_f = path.join(self.testdir, self.check_f)
        ln("-s", check_f, path.join(self.builddir, self.check_f))

    src_dir = "ccrypt-1.10"
    src_file = "ccrypt-1.10.tar.gz"
    src_uri = "http://ccrypt.sourceforge.net/download/ccrypt-1.10.tar.gz"

    def download(self):
        from benchbuild.utils.downloader import Wget
        from plumbum.cmd import tar

        with local.cwd(self.builddir):
            Wget(self.src_uri, self.src_file)
            tar('xfz', path.join(self.builddir, self.src_file))

    def configure(self):
        from benchbuild.utils.compiler import lt_clang, lt_clang_cxx
        from benchbuild.utils.run import run

        with local.cwd(self.builddir):
            clang = lt_clang(self.cflags, self.ldflags,
                             self.compiler_extension)
            clang_cxx = lt_clang_cxx(self.cflags, self.ldflags,
                                     self.compiler_extension)

        ccrypt_dir = path.join(self.builddir, self.src_dir)
        with local.cwd(ccrypt_dir):
            configure = local["./configure"]
            with local.env(CC=str(clang),
                           CXX=str(clang_cxx),
                           LDFLAGS=" ".join(self.ldflags)):
                run(configure)

    def build(self):
        from plumbum.cmd import make
        from benchbuild.utils.run import run

        ccrypt_dir = path.join(self.builddir, self.src_dir)
        with local.cwd(ccrypt_dir):
            run(make["check"])

    def run_tests(self, experiment):
        from plumbum.cmd import make
        from benchbuild.project import wrap
        from benchbuild.utils.run import run

        ccrypt_dir = path.join(self.builddir, self.src_dir)
        with local.cwd(ccrypt_dir):
            wrap(path.join(ccrypt_dir, "src", self.name), experiment)
            wrap(path.join(ccrypt_dir, "check", "crypt3-check"), experiment)
            wrap(path.join(ccrypt_dir, "check", "rijndael-check"), experiment)
            run(make["check"])
