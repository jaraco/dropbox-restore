#!/usr/bin/env python
from __future__ import print_function
import sys, os, dropbox, time
import argparse
from datetime import datetime

try:
    input = raw_input
except:
    pass

APP_KEY = 'hacwza866qep9o6'   # INSERT APP_KEY HERE
APP_SECRET = 'kgipko61g58n6uc'     # INSERT APP_SECRET HERE
DELAY = 0.2 # delay between each file (try to stay under API rate limits)

HELP_MESSAGE = \
"""Note: You must specify the path starting with "/", where "/" is the root
of your dropbox folder. So if your dropbox directory is at "/home/user/dropbox"
and you want to restore "/home/user/dropbox/folder", the ROOTPATH is "/folder".
"""

HISTORY_WARNING = \
"""Dropbox only keeps historical file versions for 30 days (unless you have
enabled extended version history). Please specify a cutoff date within the past
30 days, or if you have extended version history, you may remove this check
from the source code."""

def authorize():
    flow = dropbox.client.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = flow.start()
    print('1. Go to: ' + authorize_url)
    print('2. Click "Allow" (you might have to log in first)')
    print('3. Copy the authorization code.')
    code = input("Enter the authorization code here: ").strip()
    access_token, user_id = flow.finish(code)
    return access_token


def login(token_save_path):
    if os.path.exists(token_save_path):
        with open(token_save_path) as token_file:
            access_token = token_file.read()
    else:
        access_token = authorize()
        with open(token_save_path, 'w') as token_file:
            token_file.write(access_token)
    return dropbox.client.DropboxClient(access_token)


def parse_date(s):
    a = s.split('+')[0].strip()
    return datetime.strptime(a, '%a, %d %b %Y %H:%M:%S')


def restore_file(client, path, cutoff_datetime, is_deleted, verbose=False):
    revisions = client.revisions(path)
    revision_dict = dict((parse_date(r['modified']), r) for r in revisions)

    # skip if current revision is the same as it was at the cutoff
    if max(revision_dict.keys()) < cutoff_datetime:
        if verbose:
            print(path, 'SKIP')
        return

    # look for the most recent revision before the cutoff
    pre_cutoff_modtimes = [d for d in revision_dict.keys()
                           if d < cutoff_datetime]
    if len(pre_cutoff_modtimes) > 0:
        modtime = max(pre_cutoff_modtimes)
        rev = revision_dict[modtime]['rev']
        if verbose:
            print(path, modtime)
        client.restore(path, rev)
    else:   # there were no revisions before the cutoff, so delete
        if verbose:
            print(path, ('SKIP' if is_deleted else 'DELETE'))
        if not is_deleted:
            client.file_delete(path)


def restore_folder(client, path, cutoff_datetime, verbose=False):
    if verbose:
        print('Restoring folder:', path)
    try:
        folder = client.metadata(path, list=True,
                                 include_deleted=True)
    except dropbox.rest.ErrorResponse as e:
        print(e)
        print(HELP_MESSAGE)
        return
    for item in folder.get('contents', []):
        if item.get('is_dir', False):
            restore_folder(client, item['path'], cutoff_datetime, verbose)
        else:
            restore_file(client, item['path'], cutoff_datetime,
                         item.get('is_deleted', False), verbose)
        time.sleep(DELAY)


def date_from_string(input):
    return datetime(*map(int, input.split('-')))


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('root_path')
    parser.add_argument('cutoff', type=date_from_string)
    return parser.parse_args()


def main():
    args = get_args()
    if (datetime.now() - args.cutoff).days >= 30:
        sys.exit(HISTORY_WARNING)
    if args.cutoff > datetime.now():
        sys.exit('Cutoff date must be in the past')
    client = login('token.dat')
    restore_folder(client, args.root_path, args.cutoff, verbose=True)


if __name__ == '__main__':
    main()
