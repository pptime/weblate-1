# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2017 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import os.path
import shutil
import stat
from tarfile import TarFile
from unittest import SkipTest

from django.conf import settings

from weblate.trans.formats import FILE_FORMATS
from weblate.trans.models import Project, SubProject
from weblate.trans.search import clean_indexes
from weblate.trans.vcs import HgRepository, SubversionRepository

# Directory holding test data
TEST_DATA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'data'
)

REPOWEB_URL = \
    'https://github.com/WeblateOrg/test/blob/master/%(file)s#L%(line)s'


def get_test_file(name):
    """Return filename of test file."""
    return os.path.join(TEST_DATA, name)


def remove_readonly(func, path, _):
    "Clear the readonly bit and reattempt the removal"
    os.chmod(path, stat.S_IWRITE)
    func(path)


class RepoTestMixin(object):
    @staticmethod
    def optional_extract(output, tarname):
        """Extract test repository data if needed

        Checks whether directory exists or is older than archive.
        """

        tarname = get_test_file(tarname)

        if (not os.path.exists(output) or
                os.path.getmtime(output) < os.path.getmtime(tarname)):

            # Remove directory if outdated
            if os.path.exists(output):
                shutil.rmtree(output, onerror=remove_readonly)

            # Extract new content
            tar = TarFile(tarname)
            tar.extractall(settings.DATA_DIR)
            tar.close()

            # Update directory timestamp
            os.utime(output, None)

    def clone_test_repos(self):
        # Path where to clone remote repo for tests
        self.git_base_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-base-repo.git'
        )
        # Repository on which tests will be performed
        self.git_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-repo.git'
        )

        # Path where to clone remote repo for tests
        self.hg_base_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-base-repo.hg'
        )
        # Repository on which tests will be performed
        self.hg_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-repo.hg'
        )

        # Path where to clone remote repo for tests
        self.svn_base_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-base-repo.svn'
        )
        # Repository on which tests will be performed
        self.svn_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-repo.svn'
        )

        # Extract repo for testing
        self.optional_extract(
            self.git_base_repo_path,
            'test-base-repo.git.tar'
        )

        # Remove possibly existing directory
        if os.path.exists(self.git_repo_path):
            shutil.rmtree(self.git_repo_path, onerror=remove_readonly)

        # Create repository copy for the test
        shutil.copytree(self.git_base_repo_path, self.git_repo_path)

        # Extract repo for testing
        self.optional_extract(
            self.hg_base_repo_path,
            'test-base-repo.hg.tar'
        )

        # Remove possibly existing directory
        if os.path.exists(self.hg_repo_path):
            shutil.rmtree(self.hg_repo_path, onerror=remove_readonly)

        # Create repository copy for the test
        shutil.copytree(self.hg_base_repo_path, self.hg_repo_path)

        # Extract repo for testing
        self.optional_extract(
            self.svn_base_repo_path,
            'test-base-repo.svn.tar'
        )

        # Remove possibly existing directory
        if os.path.exists(self.svn_repo_path):
            shutil.rmtree(self.svn_repo_path, onerror=remove_readonly)

        # Create repository copy for the test
        shutil.copytree(self.svn_base_repo_path, self.svn_repo_path)

        # Remove possibly existing project directory
        test_repo_path = os.path.join(settings.DATA_DIR, 'vcs', 'test')
        if os.path.exists(test_repo_path):
            shutil.rmtree(test_repo_path, onerror=remove_readonly)

        # Remove indexes
        clean_indexes()

    def create_project(self):
        """Create test project."""
        project = Project.objects.create(
            name='Test',
            slug='test',
            web='https://weblate.org/'
        )
        self.addCleanup(shutil.rmtree, project.get_path(), True)
        return project

    def _create_subproject(self, file_format, mask, template='',
                           new_base='', vcs='git', branch=None, **kwargs):
        """Create real test subproject."""
        if file_format not in FILE_FORMATS:
            raise SkipTest(
                'File format {0} is not supported!'.format(file_format)
            )
        if 'project' not in kwargs:
            kwargs['project'] = self.create_project()

        if vcs == 'mercurial':
            d_branch = 'default'
            repo = self.hg_repo_path
            push = self.hg_repo_path
            if not HgRepository.is_supported():
                raise SkipTest('Mercurial not available!')
        elif vcs == 'subversion':
            d_branch = 'master'
            repo = 'file://' + self.svn_repo_path
            push = 'file://' + self.svn_repo_path
            if not SubversionRepository.is_supported():
                raise SkipTest('Subversion not available!')
        else:
            d_branch = 'master'
            repo = self.git_repo_path
            push = self.git_repo_path

        if 'new_lang' not in kwargs:
            kwargs['new_lang'] = 'contact'

        if 'push_on_commit' not in kwargs:
            kwargs['push_on_commit'] = False

        if branch is None:
            branch = d_branch

        return SubProject.objects.create(
            name='Test',
            slug='test',
            repo=repo,
            push=push,
            branch=branch,
            filemask=mask,
            template=template,
            file_format=file_format,
            repoweb=REPOWEB_URL,
            save_history=True,
            new_base=new_base,
            vcs=vcs,
            **kwargs
        )

    def create_subproject(self):
        """Wrapper method for providing test subproject."""
        return self._create_subproject(
            'auto',
            'po/*.po',
        )

    def create_po(self):
        return self._create_subproject(
            'po',
            'po/*.po',
        )

    def create_po_branch(self):
        return self._create_subproject(
            'po',
            'translations/*.po',
            branch='translations'
        )

    def create_po_push(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            push_on_commit=True
        )

    def create_po_empty(self):
        return self._create_subproject(
            'po',
            'po-empty/*.po',
            new_base='po-empty/hello.pot',
            new_lang='add',
        )

    def create_po_mercurial(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            vcs='mercurial'
        )

    def create_po_svn(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            vcs='subversion'
        )

    def create_po_new_base(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            new_base='po/hello.pot'
        )

    def create_po_link(self):
        return self._create_subproject(
            'po',
            'po-link/*.po',
        )

    def create_po_mono(self):
        return self._create_subproject(
            'po-mono',
            'po-mono/*.po',
            'po-mono/en.po',
        )

    def create_ts(self, suffix=''):
        return self._create_subproject(
            'ts',
            'ts{0}/*.ts'.format(suffix),
        )

    def create_ts_mono(self):
        return self._create_subproject(
            'ts',
            'ts-mono/*.ts',
            'ts-mono/en.ts',
        )

    def create_iphone(self):
        return self._create_subproject(
            'strings',
            'iphone/*.lproj/Localizable.strings',
        )

    def create_android(self):
        return self._create_subproject(
            'aresource',
            'android/values-*/strings.xml',
            'android/values/strings.xml',
        )

    def create_json(self):
        return self._create_subproject(
            'json',
            'json/*.json',
        )

    def create_json_mono(self):
        return self._create_subproject(
            'json',
            'json-mono/*.json',
            'json-mono/en.json',
        )

    def create_json_nested(self):
        return self._create_subproject(
            'json',
            'json-nested/*.json',
            'json-nested/en.json',
        )

    def create_json_webextension(self):
        return self._create_subproject(
            'webextension',
            'webextension/_locales/*/messages.json',
            'webextension/_locales/en/messages.json',
        )

    def create_joomla(self):
        return self._create_subproject(
            'joomla',
            'joomla/*.ini',
            'joomla/en-GB.ini',
        )

    def create_tsv(self):
        return self._create_subproject(
            'csv',
            'tsv/*.txt',
        )

    def create_csv(self):
        return self._create_subproject(
            'csv',
            'csv/*.txt',
        )

    def create_csv_mono(self):
        return self._create_subproject(
            'csv',
            'csv-mono/*.csv',
            'csv-mono/en.csv',
        )

    def create_php_mono(self):
        return self._create_subproject(
            'php',
            'php-mono/*.php',
            'php-mono/en.php',
        )

    def create_java(self):
        return self._create_subproject(
            'properties',
            'java/swing_messages_*.properties',
            'java/swing_messages.properties',
        )

    def create_xliff(self, name='default'):
        return self._create_subproject(
            'xliff',
            'xliff/*/{0}.xlf'.format(name),
        )

    def create_xliff_mono(self):
        return self._create_subproject(
            'xliff',
            'xliff-mono/*.xlf',
            'xliff-mono/en.xlf',
        )

    def create_resx(self):
        return self._create_subproject(
            'resx',
            'resx/*.resx',
            'resx/en.resx',
        )

    def create_yaml(self):
        return self._create_subproject(
            'yaml',
            'yml/*.yml',
            'yml/en.yml',
        )

    def create_ruby_yaml(self):
        return self._create_subproject(
            'ruby-yaml',
            'ruby-yml/*.yml',
            'ruby-yml/en.yml',
        )

    def create_link(self):
        parent = self.create_iphone()
        return SubProject.objects.create(
            name='Test2',
            slug='test2',
            project=parent.project,
            repo='weblate://test/test',
            file_format='po',
            filemask='po/*.po',
            new_lang='contact',
        )
