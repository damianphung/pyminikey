from flask import Flask
import os
import time
import json

app = Flask(__name__)

def resp(start_response, code, headers=[('Content-Type','text/html')], body=b''):
    start_response(code, headers)
    print(body)
    return body

if os.getenv('TYPE') == "master":
    volumes = os.environ['VOLUMES']

    import plyvel
    db = plyvel.DB(os.getenv('DB'), create_if_missing=True)

@app.route("/")
def master(env, start_response):
    print(env)

    key = env['REQUEST_URI']
    metakey = db.get(key.encode('utf-8'))
    
    # check value 
    if metakey is None:
        if env['REQUEST_METHOD'] == 'PUT':
            volume = volumes
            print("PUT REQUEST")
            metakey = json.dumps({"volume" : volume})

            print(metakey)
            db.put(key.encode('utf-8'), metakey.encode('utf-8'))

        else:
        # GET or DELETE
            print(key)
            return resp(start_response, '404 Not Found')
    else:
        if env['REQUEST_METHOD'] == 'PUT':
            return resp(start_response, '409 Conflict')

        if env['REQUEST_METHOD'] == 'DELETE':
            db.delete(key.encode('utf-8'))

        meta = json.loads(metakey.decode('utf-8'))
        volume = meta['volume']
    
    # redirect
    print("redirecting")
    headers = [('location', 'http://%s%s' % (volume, key)), ('expires', '0')]
    start_response('307 Found', headers)
    return [b'key redirect']



# *** Volume server

class FileCache():
    def __init__(self, basedir):
        self.basedir = basedir
        os.makedirs(basedir, exist_ok=True)
        print(f"File cache in {basedir}")

    def k2p(self, key, mkdir_ok=True):
        # md5 hash key
        assert len(key) == 32
        path = self.basedir + "/" + key[0:2] + "/" + key[0:4]
        if not os.path.isdir(path) and mkdir_ok:
            os.makedirs(path, exist_ok=True)
        return os.path.join(path, key)

    def exists(self, key):
        return os.path.isfile(self.k2p(key))

    def delete(self, key):
        return os.remove(self.k2p(key))

    def get(self, key):
        f = open(self.k2p(key), "rb")
        return f
    
    def put(self, key, value):
        with open(self.k2p(key), "wb") as f:
            f.write(value)

if os.getenv('TYPE') == "volume":
    fc = FileCache(os.environ['VOLUME'])


def volume(env, start_response):
    import hashlib

    key = env['REQUEST_URI'].encode('utf-8')
    hkey = hashlib.md5(key).hexdigest()

    
    # check value 
    if env['REQUEST_METHOD'] == 'PUT':
        flen = int(env.get('CONTENT_LENGTH', '0'))
        print(f"length = {flen}")

        if flen > 0:
            wsgi_input = env['wsgi.input']
            fc.put(hkey, wsgi_input.read(flen))
            return resp(start_response, '200 OK')
        else:
            return resp(start_response, '411 Length required')

    if not fc.exists(hkey):
        return resp(start_response, '404 Not Found')

    if env['REQUEST_METHOD'] == 'GET':
        return resp(start_response, '200 OK', body=fc.get(hkey).read())

    if env['REQUEST_METHOD'] == 'DELETE':
        fc.delete(hkey)
        return resp(start_response, '200 OK')

