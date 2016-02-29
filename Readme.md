# UoA faculty/department/user management helper

## Requirements

-   python
-   argparse

## Installation

    pip install https://github.com/UoA-eResearch/uoa-groups/archive/master.zip

## Usage

### Configuration

Before being able to use the uoa-groups script, you need to setup your ldap password. Do that by editing $HOME/.uoa-groups/config:

    [LDAP]
    username = <username>
    password = <password>
    url = uoa.auckland.ac.nz

You also need the Excel file that describes the UoA faculty/department hierarchy (I got it from HR). If you have access to Seafile you can get it from here:

https://seafile.cer.auckland.ac.nz/#group/15/lib/7529ae0b-5db9-404b-b1d9-47ab999b0e1f

Rename it if necessary, then move it to: $HOME/.uoa-groups/departments.xlsx


### Display help

    uoa-groups -h

       usage: uoa-groups [-h] {upi,search,group,all-groups} ...

       UoA directory query tool

       positional arguments:
       {upi,search,group,all-groups}
       Subcommand to run
       upi                 upi query
       search              query for names
       group               group query
       all-groups          display complete group hierarchy

       optional arguments:
       -h, --help            show this help message and exit


### Search by upi

    # quick search
    uoa-groups mbin029

    # also display groups, roles and department information
    uoa-groups upi -g -r -d mbin029

### search by name

    # search using last name (those queries can take a while, also, currently only one search term is supported)
    uoa-groups search binsteiner

    # also display groups, roles and department information
    uoa-groups search -g -r -d binsteiner

### search for group

    # search using part of group code or name
    uoa-groups group punaha

### display all groups in a hierarchy

    # simple string output, hierarchy is shown using whitespace
    uoa-groups all-groups

    # json output
    uoa-groups all-groups --json
