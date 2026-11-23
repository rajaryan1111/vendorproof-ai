import argparse
from getpass import getpass
from .auth import hasher
from .db import engine_for,query
from .config import Settings

def provision(conn,workspace,email,password,role):
    if not 12<=len(password)<=256:
        raise ValueError("Use a password of 12 to 256 characters")
    org=query(conn,"INSERT INTO organizations(name) VALUES(:name) ON CONFLICT(name) DO UPDATE SET name=excluded.name RETURNING id",name=workspace).one().id
    user=query(conn,"INSERT INTO users(email,password_hash) VALUES(:email,:hash) RETURNING id",email=email.strip().lower(),hash=hasher.hash(password)).one().id
    query(conn,"INSERT INTO memberships(user_id,organization_id,role) VALUES(:user,:org,:role)",user=user,org=org,role=role)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("email")
    parser.add_argument("role",choices=["admin","operator","reviewer","auditor"])
    args=parser.parse_args()
    password=getpass()
    with engine_for(Settings()).begin() as conn:
        provision(conn,args.workspace,args.email,password,args.role)
