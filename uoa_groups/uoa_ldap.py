'''
Python methods to query the University of Auckland LDAP directory.
'''

import sys
import ldap
import csv
from xml.dom.minidom import parseString
from blist import sortedset
from ldap.controls import SimplePagedResultsControl
from distutils.version import StrictVersion
from xml.etree.ElementTree import Element, SubElement, Comment, tostring, ElementTree
import re
import uoa_groups

# Check if we're using the Python "ldap" 2.4 or greater API
LDAP24API = StrictVersion(ldap.__version__) >= StrictVersion('2.4')

# If you're talking to LDAP, you should be using LDAPS for security!
LDAPSERVER = 'ldaps://uoa.auckland.ac.nz'
BASEDN = 'ou=People,dc=UoA,dc=auckland,dc=ac,dc=nz'
PAGESIZE = 1000
SEARCHFILTER = '(& (cn=*)(objectCategory=person)(objectClass=user)(department=*)(memberOf=CN=active.ec,OU=ec,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz))'
GROUP_REGULAR_EXPRESSION = re.compile('^CN=([A-Z]*)\.uos,OU=uos,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz$')
DEFAULT_ATTR_LIST = ['cn', 'givenName', 'department', 'sn', 'mail', 'memberOf']

STAFF_GROUP = "CN=UniStaff.ec,OU=ec,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz"
STUDENT_GROUP = "CN=Enrolled.ec,OU=ec,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz"
POSTGRAD_GROUP = "CN=Postgraduate.psrwi,OU=psrwi,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz"
DOCTORAL_STUDENT_GROUP = "CN=doctoralstudent.psrwi,OU=psrwi,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz"
CONTRACTOR_GROUP = "CN=Contractor.psrwi,OU=psrwi,OU=Groups,DC=UoA,DC=auckland,DC=ac,DC=nz"

# LDAP helper methods ++++++++++++++++++++++++++++++++++++++++

def create_controls(pagesize):
    """Create an LDAP control with a page size of "pagesize"."""
    # Initialize the LDAP controls for paging. Note that we pass ''
    # for the cookie because on first iteration, it starts out empty.
    if LDAP24API:
        return SimplePagedResultsControl(True, size=pagesize, cookie='')
    else:
        return SimplePagedResultsControl(ldap.LDAP_CONTROL_PAGE_OID, True,
                                         (pagesize, ''))

def get_pctrls(serverctrls):
    """Lookup an LDAP paged control object from the returned controls."""
    # Look through the returned controls and find the page controls.
    # This will also have our returned cookie which we need to make
    # the next search request.
    if LDAP24API:
        return [c for c in serverctrls
                if c.controlType == SimplePagedResultsControl.controlType]
    else:
        return [c for c in serverctrls
                if c.controlType == ldap.LDAP_CONTROL_PAGE_OID]

def set_cookie(lc_object, pctrls, pagesize):
    """Push latest cookie back into the page control."""
    if LDAP24API:
        cookie = pctrls[0].cookie
        lc_object.cookie = cookie
        return cookie
    else:
        est, cookie = pctrls[0].controlValue
        lc_object.controlValue = (pagesize, cookie)
        return cookie

# This is essentially a placeholder callback function. You would do your real
# work inside of this. Really this should be all abstracted into a generator...
def process_entry(dn, attrs, all_users):
    """Process an entry. The two arguments passed are the DN and
       a dictionary of attributes."""
    # print dn, attrs
    all_users[dn] = attrs

def extract_details_from_ldap_result(result):
    try:
        department = result[0][1]['department'][0]
    except KeyError:
        department = "n/a"

    givenName = result[0][1]['givenName'][0]
    sn = result[0][1]['sn'][0]
    try:
        email = result[0][1]['mail'][0]
    except KeyError:
        email = "n/a"
    cn = result[0][1]['cn'][0]
    return {'givenName': givenName, 'sn': sn, 'email': email, 'cn': cn, 'department': department}


def generate_searchfilter_person(filter):
    
        searchfilter = '(& ('+filter+')(objectCategory=person)(objectClass=user))'
        return searchfilter

def find_high_level_groups(root_group, list_of_memberships):

    if not list_of_memberships:
        return []
    
    abbrevs= [GROUP_REGULAR_EXPRESSION.match(cn).group(1) for cn in list_of_memberships if GROUP_REGULAR_EXPRESSION.match(cn)]

    return root_group.get_high_level_groups(abbrevs)


class uoa_ldap(object):
    '''Wrapper object that encapsulates important base-LDAP queries.'''

    def __init__(self, username, password):
        
        self.username = username
        self.password = password

        # Ignore server side certificate errors (assumes using LDAPS and
        # self-signed cert). Not necessary if not LDAPS or it's signed by
        # a real CA.
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
        # Don't follow referrals
        ldap.set_option(ldap.OPT_REFERRALS, 0)

        self.ldap = ldap.initialize(LDAPSERVER)
        self.ldap.protocol_version = 3          # Paged results only apply to LDAP v3
        try:
            self.ldap.simple_bind_s(self.username, self.password)
        except ldap.LDAPError as e:
            exit('LDAP bind failed: %s' % e)


    def query_ldap(self, searchfilter, attrlist):

        # Create the page control to work from
        lc = create_controls(PAGESIZE)

        all_users = {}
        # Do searches until we run out of "pages" to get from
        # the LDAP server.
        while True:
            # Send search request
            try:
                # If you leave out the ATTRLIST it'll return all attributes
                # which you have permissions to access. You may want to adjust
                # the scope level as well (perhaps "ldap.SCOPE_SUBTREE", but
                # it can reduce performance if you don't need it).
                msgid = self.ldap.search_ext(BASEDN, ldap.SCOPE_ONELEVEL, searchfilter,
                                     attrlist, serverctrls=[lc])
            except ldap.LDAPError as e:
                raise Exception('LDAP search failed: %s' % e)

            # Pull the results from the search request
            try:
                rtype, rdata, rmsgid, serverctrls = self.ldap.result3(msgid)
            except ldap.LDAPError as e:
                raise Exception('Could not pull LDAP results: %s' % e)

            # Each "rdata" is a tuple of the form (dn, attrs), where dn is
            # a string containing the DN (distinguished name) of the entry,
            # and attrs is a dictionary containing the attributes associated
            # with the entry. The keys of attrs are strings, and the associated
            # values are lists of strings.
            for dn, attrs in rdata:
                process_entry(dn, attrs, all_users)

            # Get cookie for next request
            pctrls = get_pctrls(serverctrls)
            if not pctrls:
                print >> sys.stderr, 'Warning: Server ignores RFC 2696 control.'
                break
            # Ok, we did find the page control, yank the cookie from it and
            # insert it into the control for our next search. If however there
            # is no cookie, we are done!
            cookie = set_cookie(lc, pctrls, PAGESIZE)
            if not cookie:
                break

        return all_users

    def close_ldap(self):
        """Call this once you are finished querying."""
        
        self.ldap.unbind()

    def get_all_users_of_group(self, group, attr_list=DEFAULT_ATTR_LIST):
        """Finds all active users."""

        searchfilter = "(memberOf={})".format(group)

        results = self.query_ldap(searchfilter, attr_list)

        if len(results) == 0:
            return None
        else:
            return results

    def find_upi(self, upi, attr_list=DEFAULT_ATTR_LIST):
        """Finds the user with this exact upi."""

        searchfilter = '(& (cn='+upi+')(objectCategory=person)(objectClass=user))'
        results = self.query_ldap(searchfilter, attr_list)

        if len(results) == 0:
            return None
        elif len(results) == 1:
            return results[results.keys()[0]]
        else:
            raise Exception("More than one match found.")
        

    def list_groups_for_upi(self, upi):
        """List all the UoA groups this upi is member of."""

        user = self.find_upi(upi, ['memberOf'])
        return find_high_level_groups(user['memberOf'])

        
    def find_matching_upis(self, upi_search_string, attr_list=DEFAULT_ATTR_LIST):
        """Returns all matching ldap entries as a dict with the dn as key and a properties map as value (using the attribute list as keys)."""

        searchfilter = '(& (cn='+upi_search_string+')(objectCategory=person)(objectClass=user))'

        results = self.query_ldap(ldap, searchfilter, attr_list)

        return results

        
    def get_user_details(upi, attr_list=DEFAULT_ATTR_LIST):
        """Return all associated LDAP properties for a user/upi."""

        try:
            searchfilter = '(cn='+upi+')'
            ldap_result_id = self.ldap.search(BASEDN, ldap.SCOPE_SUBTREE, searchfilter, attr_list)
            result_set = []
            while 1:
                result_type, result_data = self.ldap.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    # if you are expecting multiple results you can append them
                    # otherwise you can just wait until the initial result and break out
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)
            return result_set
        except ldap.LDAPError as e:
            raise Exception("Could not get user details: %s" % e)

    def search_user_first_last_name(givenName, surname, attr_list=DEFAULT_ATTR_LIST):
        """Performs a LDAP query for a first & last name."""

        try:
            searchfilter = '(&(sn='+surname+')(givenName='+givenName+'))'
            ldap_result_id = self.ldap.search(BASEDN, ldap.SCOPE_SUBTREE, searchfilter, attr_list)
            result_set = []
            while 1:
                result_type, result_data = self.ldap.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    # if you are expecting multiple results you can append them
                    # otherwise you can just wait until the initial result and break out
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)
                        
            return result_set
        except ldap.LDAPError as e:
            raise Exception("Could not search for user: %s" % e)


    def search_user(self, search_term, attr_list=DEFAULT_ATTR_LIST):
        """Performs a LDAP query for a first & last name."""

        try:
            searchfilter = generate_searchfilter_person('displayName='+search_term)
            ldap_result_id = self.ldap.search(BASEDN, ldap.SCOPE_SUBTREE, searchfilter, attr_list)
            result_set = []
            while 1:
                result_type, result_data = self.ldap.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    # if you are expecting multiple results you can append them
                    # otherwise you can just wait until the initial result and break out
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)
                        
            return result_set
        except ldap.LDAPError as e:
            raise Exception("Could not search for user: %s" % e)
        
