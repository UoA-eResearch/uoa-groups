"""

Command line interface for UoA directory and people queries

"""

import logging
import sys
import argparse
from uoa_models import researcher, pretty_print_researcher
import uoa_groups
import getpass
import os.path
import ConfigParser
from uoa_groups import UoA_groups
from uoa_ldap import uoa_ldap
import traceback
import json

CONF_FOLDERNAME = 'uoa-groups'
CONF_FILENAME = 'config'
CONF_UOAGROUPS_FILENAME = 'departments.xlsx'
CONF_SYS = os.path.join('/etc/', CONF_FOLDERNAME)
CONF_HOME = os.path.join(os.path.expanduser('~'), '.'+CONF_FOLDERNAME)
CONF_SYS_CONFIG = os.path.join(CONF_SYS, CONF_FILENAME)
CONF_SYS_UOAGROUPS = os.path.join(CONF_SYS, CONF_UOAGROUPS_FILENAME)
CONF_HOME_CONFIG = os.path.join(CONF_HOME, CONF_FILENAME)
CONF_HOME_UOAGROUPS = os.path.join(CONF_HOME, CONF_UOAGROUPS_FILENAME)

# arg parsing ========================================
class CliCommands(object):

    def __init__(self):

        self.config = ProjectConfig()

        parser = argparse.ArgumentParser(
            description='UoA directory query tool')

        subparsers = parser.add_subparsers(help='Subcommand to run')

        upi_parser = subparsers.add_parser('upi', help="upi query")
        upi_parser.add_argument('--groups', '-g', help="Display groups.", action='store_true')
        upi_parser.add_argument('--roles', '-r', help="Display roles.", action='store_true')
        upi_parser.add_argument('--department', '-d', help="Department entry in LDAP (beware, this is usually not very reliable)", action='store_true')
        upi_parser.add_argument('upi', metavar='<upi>', type=unicode, nargs=1, help='the upi to query')
        upi_parser.set_defaults(func=self.upi, command='upi')

        search_parser = subparsers.add_parser('search', help="query for names")
        search_parser.add_argument('--groups', '-g', help="Display groups.", action='store_true')
        search_parser.add_argument('--roles', '-r', help="Display roles.", action='store_true')
        search_parser.add_argument('--department', '-d', help="Department entry in LDAP (beware, this is usually not very reliable)", action='store_true')
        search_parser.add_argument('search', metavar='<search-term>', type=unicode, nargs=1, help='the search term')
        search_parser.set_defaults(func=self.search, command='search')


        group_parser = subparsers.add_parser('group', help='group query')
        group_parser.add_argument('--id', help="Only query exact group id.", action='store_true')
        # group_parser.add_argument('--all', '-a', help="Print the complete group hierarchy.",  action='store_true')
        group_parser.add_argument('group', metavar='<group>', type=unicode, nargs=1, help='the group to query, will first try to find exact group id match (ignore-case -- 1 result in this case), if it can\'t find anything will use search term against group names too (ignore-case) and list all matches.')
        group_parser.set_defaults(func=self.group, command='group')

        all_groups_parser = subparsers.add_parser('all-groups', help='display complete group hierarchy')
        all_groups_parser.add_argument('--json', '-j', help='output in json format', action='store_true')
        all_groups_parser.set_defaults(func=self.all_groups, command='all-groups')

        self.namespace = parser.parse_args()

        try:
            self.namespace.func(self.namespace)
        except Exception as e:
            print e
            traceback.print_exc()
            sys.exit(0)


    def all_groups(self, args):


        if args.json:

            hierarchy = {}
            root = self.config.uoa_groups.root
            hierarchy['name'] = root.name
            hierarchy['code'] = root.gid
            hierarchy['divisions'] = []

            for division in root.childs:

                div_hierarchy = {}
                div_hierarchy['name'] = division.name
                div_hierarchy['code'] = division.gid
                div_hierarchy['departments'] = []

                # flattening the rest of the department structure, also, we can asume there are only 3 levels of departments
                for dep in division.childs:
                    dep_hierarchy = {}
                    dep_hierarchy['name'] = dep.name
                    dep_hierarchy['code'] = dep.gid
                    div_hierarchy['departments'].append(dep_hierarchy)
                    for depL2 in dep.childs:
                        depL2_hierarchy = {}
                        depL2_hierarchy['name'] = depL2.name
                        depL2_hierarchy['code'] = depL2.gid
                        div_hierarchy['departments'].append(depL2_hierarchy)
                        for depL3 in dep.childs:
                            depL3_hierarchy = {}
                            depL3_hierarchy['name'] = depL3.name
                            depL3_hierarchy['code'] = depL3.gid
                            div_hierarchy['departments'].append(depL3_hierarchy)

                hierarchy['divisions'].append(div_hierarchy)

            json_string = json.dumps(hierarchy, indent=2)
            print ""
            print json_string
            print ""

        else:
            print ""
            self.config.uoa_groups.print_tree()
            print ""

    def group(self,args):

        print ""
        if args.id:
            group = self.config.uoa_groups.get_group(args.group[0], True)
            if group:
                group.print_tree_down()
                print ""

        else:
            groups = self.config.uoa_groups.find_groups(args.group[0], True)

            for g in groups:
                g.print_tree_down()
                print ""


    def get_ldap(self):

        ldap_user = self.config.ldap_user

        if not ldap_user:
            ldap_user = raw_input("LDAP username: ")
            if not ldap_user:
                print "No ldap username specified, exiting..."
                sys.exit(0)

        ldap_password = self.config.ldap_password
        if not ldap_password:
            ldap_password = getpass.getpass()

        ldap = uoa_ldap(ldap_user, ldap_password)
        return ldap


    def search(self, args):

        ldap = self.get_ldap()

        users = ldap.search_user("*"+args.search[0]+"*")

        for u in users:

            res = researcher.from_ldap_entry(u[0][1], self.config.uoa_groups)
            pretty_print_researcher(res, args.roles, args.groups, args.department)
            print "        -----------           "

        print ""

    def upi(self, args):

        ldap = self.get_ldap()

        user = researcher.from_upi(args.upi[0], self.config.uoa_groups, ldap)

        pretty_print_researcher(user, args.roles, args.groups, args.department)

class ProjectConfig(object):

    def __init__(self):

        if os.path.exists(CONF_HOME_UOAGROUPS):
            self.uoagroups_file = CONF_HOME_UOAGROUPS
        elif os.path.exists(CONF_SYS_UOAGROUPS):
            self.uoagroups_file = CONF_SYS_UOAGROUPS
        else:
            print "No groups file found. Please copy it to either: {} or {}".format(CONF_HOME_UOAGROUPS, CONF_SYS_UOAGROUPS)
            sys.exit(1)

        self.uoa_groups = UoA_groups(self.uoagroups_file)

        config = ConfigParser.SafeConfigParser()

        try:
            user = os.environ['SUDO_USER']
            conf_user = os.path.join(os.path.expanduser('~'+user), "/."+CONF_FOLDERNAME, CONF_FILENAME)
            candidates = [CONF_SYS_CONFIG, conf_user, CONF_HOME_CONFIG]
        except KeyError:
            candidates = [CONF_SYS_CONFIG, CONF_HOME_CONFIG]

        config.read(candidates)

        try:
            self.ldap_user = config.get('LDAP', 'username')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            # print "No LDAP username configured. Check 'https://github.com/UoA-eResearch/uoa-groups' for more details."
            self.ldap_user = None

        try:
            self.ldap_password = config.get('LDAP', 'password')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            # print "No LDAP password configured. Check 'https://github.com/UoA-eResearch/uoa-groups' for more details."
            self.ldap_password = None


        try:
            self.ldap_url = config.get('LDAP', 'url')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            # print "No LDAP url configured. Check 'https://github.com/UoA-eResearch/uoa-groups' for more details."
            self.ldap_url = None

        

def run():
    CliCommands()

