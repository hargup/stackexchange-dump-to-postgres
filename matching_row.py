# Read a row, if it is in the questionId, answerId thingy print it
import lxml.etree
import sys

def row_to_id(row_string):
    try:
        # print(row_string)
        elem = lxml.etree.fromstring(row_string)
        return elem.get('Id')
    except:
        return ""

def read_required_ids(filepath="./qaIds.txt"):
    ids = []
    with open(filepath) as fp:
        ids = [line.strip() for line in fp.readlines()]
    return ids

ids = read_required_ids()
# print("Read the ids")
row = input()
# print("Read rows")
while row:
    id_ = row_to_id(row.strip())
    # print(f'Got id:', id_)
    if id_ in ids:
        print(row.strip())
    row = input()

