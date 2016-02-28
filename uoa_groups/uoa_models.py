from xml.etree.ElementTree import Element, SubElement, Comment, tostring, ElementTree
from uoa_ldap import STAFF_GROUP, STUDENT_GROUP, POSTGRAD_GROUP, DOCTORAL_STUDENT_GROUP, CONTRACTOR_GROUP
from uoa_ldap import find_high_level_groups

def enc(text):
    return text.decode('unicode_escape').encode('iso8859-1').decode('utf-8')


def pretty_print_researcher(researcher, print_roles, print_groups, print_department):

    print ""
    print "First name: "+researcher.first_name
    print "Last name: "+researcher.last_name

    print "Email: "+ researcher.mail
    print "UPI: "+researcher.cn
    print "Tuakiri username: "+researcher.tuakiri_username

    if print_roles:
        print ""
        print "Roles:"
        print "\tStaff: "+str(researcher.is_staff)
        print "\tStudent: "+str(researcher.is_student)
        print "\tPostgrad: "+str(researcher.is_postgrad)
        print "\tDoctoral student: "+str(researcher.is_doctoral_student)
        print "\tContractor: "+str(researcher.is_contractor)

    if print_groups:
        print ""
        print "Groups:"
        if not researcher.groups:
            print "\tNo groups"
        else:
            for g in researcher.groups:
                g.print_tree_down("\t")


    if print_department:
        print ""
        print "Department:"
        print "\t"+researcher.department

    print ""


class researcher():
    '''Object to encapsulate all relevant details for a researcher, including associated groups.'''

    @classmethod
    def from_upi(cls, upi, root_group, ldap):
        '''
        Creates a researcher object from upi, using the provided group hierarchy for group information.
        '''
        ldap_entry = ldap.find_upi(upi)
        if not ldap_entry:
            raise Exception("No entry found for upi: "+str(upi))

        return cls.from_ldap_entry(ldap_entry, root_group)

    @classmethod
    def from_ldap_entry(cls, ldap_entry, root_group):
        if ldap_entry.get('department', None):
            if len(ldap_entry['department']) == 1:
                dep = ldap_entry['department'][0]
            else:
                dep = 'n/a'
        else:
            dep = 'n/a'

        return cls(ldap_entry['cn'], ldap_entry['givenName'], ldap_entry.get('sn', 'n/a'), ldap_entry.get('mail', None), dep, ldap_entry.get('memberOf'), root_group)

    def __init__(self, cn, first_name, last_name, mail, department, memberships, root_group):
        self.cn = cn[0]
        self.tuakiri_username = str(self.cn) + "@auckland.ac.nz"
        self.first_name = first_name[0]
        self.last_name = last_name[0]
        if mail:
            self.mail = mail[0]
        else:
            self.mail = self.cn + "@aucklanduni.co.nz"
            
        self.department = department

        if memberships:
            self.groups = find_high_level_groups(root_group, memberships)

            self.is_staff = STAFF_GROUP in  memberships
            self.is_student = STUDENT_GROUP in memberships
            self.is_postgrad = POSTGRAD_GROUP in memberships
            self.is_doctoral_student = DOCTORAL_STUDENT_GROUP in memberships
            self.is_contractor = CONTRACTOR_GROUP in memberships

        else:
            self.groups = []
            self.is_staff = False
            self.is_student = False
            self.is_postgrad = False
            self.is_doctoral_student = False
            self.is_contractor = False
            
    def __str__(self):
        return self.tuakiri_username + ": " + self.first_name + " " + self.last_name

    def add_to_xml_record(self, xml_root):
        """For figshare export, might be moved to a different class in the future."""
        
        record = SubElement(xml_root, 'Record')
        uniqueId = SubElement(record, 'UniqueID')
        uniqueId.text = self.tuakiri_username
        firstName = SubElement(record, 'FirstName')
        firstName.text = enc(self.first_name)
        lastName = SubElement(record, 'LastName')
        lastName.text = enc(self.last_name)
        email = SubElement(record, 'Email')
        email.text = enc(self.mail)
        userQuota = SubElement(record, 'UserQuota')
        userQuota.text = self.quota
        userAssoc = SubElement(record, 'UserAssociationCriteria')
        if self.department_short == 'n/a':
            userAssoc.text = enc('unassociated')
        else:
            userAssoc.text = enc(self.department_short)
        isActive = SubElement(record, 'IsActive')
        isActive.text = self.isActive
