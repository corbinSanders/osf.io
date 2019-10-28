import logging
import csv
import datetime
import json
import os
import shutil
import re
import jsonschema
import argparse

from jsonschema.exceptions import ValidationError

from website.project.metadata.utils import create_jsonschema_from_metaschema
from website.project.metadata.schemas import ensure_schema_structure, from_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('-a', '--authorsource', help='Specify the source file for the author csv file')
parser.add_argument('-r', '--registrysource', help='Specify the source file for the registrty csv file')
parser.add_argument('-t', '--target', help='Specify the target directory of the registry directories')
parser.add_argument('-d', '--dry', action='store_true', help='Dry run: Have the script delete the target directory after completion')

schema_to_spreadsheet_mapping = [
    {'q1': 'TITLE'},
    {'q2': 'B2 AUTHORS'},
    {'q3': 'ID'},
    {'q4': 'POST DATE'},
    {'q5': 'B3 ACKNOWLEDGEMENTS'},
    {'q6': 'B4 FACULTY MEMBER?'},
    {'q8': 'B5 PROSPECTIVE OR RETROSPECTIVE?'},
    {'q10': 'B6 EXPERIMENTAL STUDY?'},
    {'q11': 'B7 DATE OF START OF STUDY'},
    {'q12': 'B8 GATE DATE'},
    {'q13': 'B9 PRESENTED AT EGAP MEETING?'},
    {'q14': 'B10 PRE-ANALYSIS PLAN WITH REGISTRATION?'},
    {'q15': 'C1 BACKGROUND'},
    {'q16': 'C2 HYPOTHESES'},
    {'q17': 'C3 TESTING PLAN'},
    {'q18': 'C4 COUNTRY'},
    {'q19': 'C5 SAMPLE SIZE'},
    {'q20': 'C6 POWER ANALYSIS?'},
    {'q22': 'C7 IRB APPROVAL?'},
    {'q24': 'C8 IRB NUMBER'},
    {'q25': 'C9 DATE OF IRB APPROVAL'},
    {'q26': 'C10 INTERVENTION IMPLEMENTER'},
    {'q28': 'C11 REMUNERATION?'},
    {'q30': 'C12 PUBLICATION AGREEMENT?'},
    {'q32': 'C13 JEL CODES'},
    {'q33': 'METHODOLOGY'},
    {'q34': 'POLICY'},
]

# Any multiple choice questions where "Other" is a possible response, have subsequent "Other"
# question to log that response.  If multiple choice question value is invalid,
# attempt to log the value in the corresponding "Other" question response.
other_mapping = {
    'q6': 'q7',
    'q8': 'q9',
    'q20': 'q21',
    'q22': 'q23',
    'q26': 'q27',
    'q28': 'q29',
    'q30': 'q31'
}

def create_file_tree_and_json(author_source, registry_source, target):
    # Things this function needs to do:
    # For each row in the registry function, create a directory.
    # Create two JSON files, one project json with ID, Title, Postdate, and authors listed
    # with emails. And another with all the key value pairs for the registry meta.
    top_dir = target
    logger.info('Creating EGAP directory at {}'.format(top_dir))
    os.mkdir(top_dir)
    author_list = create_author_dict(author_source)
    with open(registry_source) as csv_registry_file:
        csv_reader = csv.reader(csv_registry_file, delimiter=',')
        header_row = next(csv_reader)
        normalized_header_row = [col_header.decode('ascii', 'ignore') for col_header in header_row]

        id_index = normalized_header_row.index('ID')
        for line in csv_reader:
            row = [cell.decode('ascii', 'ignore') for cell in line]
            project_id = row[id_index]
            logger.info('Adding project ID: {}'.format(project_id))
            root_directory = os.path.join(top_dir, project_id)
            os.mkdir(root_directory)
            data_directory = os.path.join(root_directory, 'data')
            os.mkdir(data_directory)
            os.mkdir(os.path.join(data_directory, 'nonanonymous'))
            project_dict = make_project_dict(row, author_list, normalized_header_row)
            make_json_file(root_directory, project_dict, 'project')
            registration_dict = make_registration_dict(row, normalized_header_row)
            make_json_file(root_directory, registration_dict, 'registration')

def create_author_dict(source):
    # Reads in author CSV and returns a list of dicts with names and emails of EGAP Authors
    authors = []
    with open(source) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        header_row = next(csv_reader)
        normalized_header_row = [col_header.decode('ascii', 'ignore').strip() for col_header in header_row]

        name_index = normalized_header_row.index('Name')
        email_index = normalized_header_row.index('Email')
        for line in csv_reader:
            row = [cell.decode('ascii', 'ignore') for cell in line]
            logger.info('Adding user: ' + row[name_index])
            if row[email_index] != '':
                author_dict = {'name': row[name_index].strip(), 'email': row[email_index]}
            else:
                author_dict = {'name': row[name_index].strip()}
            authors.append(author_dict)
    return authors

def make_project_dict(row, author_list, normalized_header_row):
    project = {}
    title_index = normalized_header_row.index('TITLE')
    id_index = normalized_header_row.index('ID')
    postdate_index = normalized_header_row.index('POST DATE')
    contributors_index = normalized_header_row.index('B2 AUTHORS')
    project['id'] = row[id_index]
    project['title'] = row[title_index]
    project['post-date'] = row[postdate_index]

    authors = row[contributors_index]

    authors = authors.split('|')
    project['contributors'] = []
    author_name_list = [author['name'] for author in author_list]
    for author in authors:
        author = author.strip()
        if author:
            if author not in author_name_list:
                logger.warning('Author {} not in Author spreadsheet for project {}.'.format(author,row[id_index]))
                project['contributors'].append({'name': author})
            else:
                author_list_index = author_name_list.index(author)
                project['contributors'].append(author_list[author_list_index])
    return project

def make_registration_dict(row, normalized_header_row):
    registration = {}

    for question in schema_to_spreadsheet_mapping:
        qid = question.keys()[0]
        column_name = question.values()[0].strip("\"")
        value = build_question_response(normalized_header_row, row, qid, column_name)
        validated_qid, other_response = validate_response(qid, value)
        registration[validated_qid] = value
        if other_response:
            registration[other_response] = build_nested_response('Other (describe in text box below)')
    # q35 and q36 are required questions at the end of the schema, certification and
    # confirmation questions. Just marking as agree -
    registration['q35'] = build_nested_response('Agree')
    registration['q36'] = build_nested_response('Agree')
    return registration

def make_json_file(filepath, data, json_type):
    if json_type == 'project':
        filepath = filepath + '/project.json'
    if json_type == 'registration':
        filepath = filepath + '/registration-schema.json'
    with open(filepath, 'w') as outfile:
        json.dump(data, outfile)

def build_question_response(header_row, row, question_key, column_title):
    """Format the question's response to go in the registration_metadata
    :param header_row: Header row in spreadsheet
    :param row: Row in spreadsheet
    :param question_key: string, Official question key as part of schema
    :param column_title: string, Corresponding question_key column title in EGAP spreadsheet
    """
    index = header_row.index(column_title)
    value = clean_value(row[index])
    # Spreadsheet has these as comma-separated values, but looking for array
    if question_key in ['q33', 'q34']:
        value = value.split(', ')
    return build_nested_response(value)

def clean_value(value):
    """Clean spreadsheet values of issues that will affect validation """
    value = value.strip("\"")
    if value == 'n/a':
        return 'N/A'
    elif value == 'Design was registered before field was added':
        return ''
    return value

def build_nested_response(value):
    return {
        'comments': [],
        'extra': [],
        'value': value
    }

def validate_response(qid, value):
    """Validate question response

    Validating each question response individually.  If there is an error, we will
    attempt to add the value to the corresponding "Other" block.  Return that question id instead.

    For example, q6 is a multiple choice question, with "Other" as a choice.  If text is entered
    for q6 that does not match one of the multiple choice answers, assuming that this is "other"
    text, and this response should go to the corresponding q7 question.  q6 will be marked
    as "Other"

    :param qid: string, question id from schema
    :param value: question response
    :param draft: DraftRegistration
    :return qid: tuple, (qid corresponding to value, optional "Other" qid)
    """
    temporary_check = {}
    temporary_check[qid] = value
    egap_schema = ensure_schema_structure(from_json('egap-registration.json'))
    schema = create_jsonschema_from_metaschema(egap_schema,
        required_fields=False,
        is_reviewer=False)

    try:
        json_schema = jsonschema.validate(temporary_check, schema)
    except ValidationError as exc:
        if qid in other_mapping:
            return other_mapping[qid], qid
        else:
            raise Exception(exc)
    return qid, None

def main(default_args=False):
    if default_args:
        args = parser.parse_args(['--source', 'default', '--target', 'default'])
    else:
        args = parser.parse_args()

    author_source = args.authorsource
    registry_source = args.registrysource
    target_directory = args.target
    dry_run = args.dry

    if not author_source:
        author_source = 'EGAP_author_emails.csv'

    if not registry_source:
        registry_source = 'EGAP_registry_for_OSF.csv'

    if not target_directory:
        target_directory = 'EGAP_data_{}'.format(datetime.datetime.now().strftime('%m-%d-%Y'))

    create_file_tree_and_json(author_source, registry_source, target_directory)

    if dry_run:
        shutil.rmtree(target_directory)
        raise RuntimeError('Dry run, file tree being deleted.')

if __name__ == '__main__':

    main(default_args=False)
