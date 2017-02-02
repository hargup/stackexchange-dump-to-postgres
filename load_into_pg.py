#!/usr/bin/env python
import sys
import time
import argparse
import psycopg2 as pg
import row_processor as Processor
import six

# Special rules needed for certain tables (esp. for old database dumps)
specialRules = {
    ('Posts', 'ViewCount'): "NULLIF(%(ViewCount)s, '')::int"
}

def _makeDefValues(keys):
    """Returns a dictionary containing None for all keys."""
    return dict(( (k, None) for k in keys ))

def _createMogrificationTemplate(table, keys):
    """Return the template string for mogrification for the given keys."""
    return ( '(' +
             ', '.join( [ '%(' + k + ')s' if (table, k) not in specialRules else specialRules[table, k]
                          for k in keys
                        ]
                      ) +
             ')'
           )

def _createCmdTuple(cursor, keys, templ, attribs):
    """Use the cursor to mogrify a tuple of data.
    The passed data in `attribs` is augmented with default data (NULLs) and the
    order of data in the tuple is the same as in the list of `keys`. The
    `cursor` is used toe mogrify the data and the `templ` is the template used
    for the mogrification.
    """
    defs = _makeDefValues(keys)
    defs.update(attribs)
    return cursor.mogrify(templ, defs)

def handleTable(table, keys, dbname, mbDbFile, mbHost, mbPort, mbUsername, mbPassword):
    """Handle the table including the post/pre processing."""
    dbFile     = mbDbFile if mbDbFile is not None else table + '.xml'
    tmpl       = _createMogrificationTemplate(table, keys)
    start_time = time.time()

    try:
        pre    = open('./sql/' + table + '_pre.sql').read()
        post   = open('./sql/' + table + '_post.sql').read()
    except IOError as e:
        six.print_("Could not load pre/post sql. Are you running from the correct path?", file=sys.stderr)
        sys.exit(-1)

    dbConnectionParam = "dbname={}".format(dbname)

    if mbPort is not None:
        dbConnectionParam += ' port={}'.format(mbPort)

    if mbHost is not None:
        dbConnectionParam += ' host={}'.format(mbHost)

    # TODO Is the escaping done here correct?
    if mbUsername is not None:
        dbConnectionParam += ' user={}'.format(mbUsername)

    # TODO Is the escaping done here correct?
    if mbPassword is not None:
        dbConnectionParam += ' password={}'.format(mbPassword)

    try:
        with pg.connect(dbConnectionParam) as conn:
            with conn.cursor() as cur:
                try:
                    with open(dbFile, 'rb') as xml:
                        # Pre-processing (dropping/creation of tables)
                        six.print_('Pre-processing ...')
                        if pre != '':
                            cur.execute(pre)
                            conn.commit()
                        six.print_('Pre-processing took {:.1f} seconds'.format(time.time() - start_time))

                        # Handle content of the table
                        start_time = time.time()
                        six.print_('Processing data ...')
                        for rows in Processor.batch(Processor.parse(xml), 500):
                            valuesStr = ',\n'.join(
                                            [ _createCmdTuple(cur, keys, tmpl, row_attribs).decode('utf-8')
                                                for row_attribs in rows
                                            ]
                                        )

                            if len(valuesStr) > 0:
                                cmd = 'INSERT INTO ' + table + \
                                      ' VALUES\n' + valuesStr + ';'
                                cur.execute(cmd)
                                conn.commit()
                        six.print_('Table processing took {:.1f} seconds'.format(time.time() - start_time))

                        # Post-processing (creation of indexes)
                        start_time = time.time()
                        six.print_('Post processing ...')
                        if post != '':
                            cur.execute(post)
                            conn.commit()
                        six.print_('Post processing took {} seconds'.format(time.time() - start_time))

                except IOError as e:
                    six.print_("Could not read from file {}.".format(dbFile), file=sys.stderr)
                    six.print_("IOError: {0}".format(e.strerror), file=sys.stderr)
    except pg.Error as e:
        six.print_("Error in dealing with the database.", file=sys.stderr)
        six.print_("pg.Error ({0}): {1}".format(e.pgcode, e.pgerror), file=sys.stderr)
        six.print_(str(e), file=sys.stderr)
    except pg.Warning as w:
        six.print_("Warning from the database.", file=sys.stderr)
        six.print_("pg.Warning: {0}".format(str(w)), file=sys.stderr)



#############################################################

parser = argparse.ArgumentParser()
parser.add_argument( 'table'
                   , help    = 'The table to work on.'
                   , choices = ['Users', 'Badges', 'Posts', 'Tags', 'Votes', 'PostLinks', 'PostHistory', 'Comments']
                   )

parser.add_argument( '-d', '--dbname'
                   , help    = 'Name of database to create the table in. The database must exist.'
                   , default = 'stackoverflow'
                   )

parser.add_argument( '-f', '--file'
                   , help    = 'Name of the file to extract data from.'
                   , default = None
                   )

parser.add_argument( '-u', '--username'
                   , help    = 'Username for the database.'
                   , default = None
                   )

parser.add_argument( '-p', '--password'
                   , help    = 'Password for the database.'
                   , default = None
                   )

parser.add_argument( '-P', '--port'
                   , help    = 'Port to connect with the database on.'
                   , default = None
                   )

parser.add_argument( '-H', '--host'
                   , help    = 'Hostname for the database.'
                   , default = None
                   )

parser.add_argument( '--with-post-body'
                   , help   = 'Import the posts with the post body. Only used if importing Posts.xml'
                   , action = 'store_true'
                   , default = False
                   )

args = parser.parse_args()

table = args.table
keys = None

if table == 'Users':
    keys = [
        'Id'
      , 'Reputation'
      , 'CreationDate'
      , 'DisplayName'
      , 'LastAccessDate'
      , 'WebsiteUrl'
      , 'Location'
      , 'AboutMe'
      , 'Views'
      , 'UpVotes'
      , 'DownVotes'
      , 'ProfileImageUrl'
      , 'Age'
      , 'AccountId'
    ]
elif table == 'Badges':
    keys = [
        'Id'
      , 'UserId'
      , 'Name'
      , 'Date'
    ]
elif table == 'PostLinks':
    keys = [
        'Id'
      , 'CreationDate'
      , 'PostId'
      , 'RelatedPostId'
      , 'LinkTypeId'
    ]
elif table == 'Comments':
    keys = [
        'Id'
      , 'PostId'
      , 'Score'
      , 'Text'
      , 'CreationDate'
      , 'UserId'
    ]
elif table == 'Votes':
    keys = [
        'Id'
      , 'PostId'
      , 'VoteTypeId'
      , 'UserId'
      , 'CreationDate'
      , 'BountyAmount'
    ]
elif table == 'Posts':
    keys = [
        'Id'
      , 'PostTypeId'
      , 'AcceptedAnswerId'
      , 'ParentId'
      , 'CreationDate'
      , 'Score'
      , 'ViewCount'
      , 'Body'
      , 'OwnerUserId'
      , 'LastEditorUserId'
      , 'LastEditorDisplayName'
      , 'LastEditDate'
      , 'LastActivityDate'
      , 'Title'
      , 'Tags'
      , 'AnswerCount'
      , 'CommentCount'
      , 'FavoriteCount'
      , 'ClosedDate'
      , 'CommunityOwnedDate'
    ]

    # If the user has not explicitly asked for loading the body, we replace it with NULL
    if not args.with_post_body:
        specialRules[('Posts', 'Body')] = 'NULL'

elif table == 'Tags':
    keys = [
        'Id'
      , 'TagName'
      , 'Count'
      , 'ExcerptPostId'
      , 'WikiPostId'
    ]
elif table == 'PostHistory':
    keys = [
        'Id',
        'PostHistoryTypeId',
        'PostId',
        'RevisionGUID',
        'CreationDate',
        'UserId',
        'Text'
    ]
elif table == 'Comments':
    keys = [
        'Id',
        'PostId',
        'Score',
        'Text',
        'CreationDate',
        'UserId',
    ]

try:
    # Python 2/3 compatibility
    input = raw_input
except NameError:
    pass

choice = input('This will drop the {} table. Are you sure [y/n]?'.format(table))

if len(choice) > 0 and choice[0].lower() == 'y':
    handleTable(table, keys, args.dbname, args.file, args.host, args.port, args.username, args.password)
else:
    six.print_("Cancelled.")

