"""Local administrator password reset. Requires file-system access; no reset API."""
import argparse
from getpass import getpass
from pathlib import Path
import os
from app import BASE_DIR, load_local_env
from database import connect,password_hash


def main():
    load_local_env()
    parser=argparse.ArgumentParser(description='Change an existing BreadStore admin password from this PC.')
    parser.add_argument('--email',default=os.getenv('ADMIN_EMAIL','admin@breadstore.local'),help='Existing admin email')
    parser.add_argument('--db',default=os.getenv('DB_PATH',str(BASE_DIR/'data'/'breadstore.db')),help='Database path')
    args=parser.parse_args()
    password=getpass('New password (12+ characters): ')
    confirmation=getpass('Repeat new password: ')
    if len(password)<12 or password!=confirmation:
        raise SystemExit('Password must contain 12+ characters and both entries must match.')
    db_path=Path(args.db)
    if not db_path.is_file():
        raise SystemExit(f'Database not found: {db_path}')
    digest,salt=password_hash(password)
    with connect(db_path) as cn:
        existing=cn.execute('SELECT id FROM users WHERE email=?',(args.email,)).fetchone()
        if not existing:
            raise SystemExit(f'No administrator account matches {args.email}')
        cn.execute('UPDATE users SET password_hash=?,salt=? WHERE id=?',(digest,salt,existing['id']))
        cn.execute('DELETE FROM sessions WHERE user_id=?',(existing['id'],))
    print('Password reset successfully. All existing sessions have been signed out.')

if __name__=='__main__':
    main()
