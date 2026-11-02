import sys, json, urllib.request, uuid; sys.path.insert(0,'.')
from bs import call, B, _op
def add(path,name,tags):
    bnd=uuid.uuid4().hex; fn=path.split('/')[-1]
    body=(f"--{bnd}\r\nContent-Disposition: form-data; name=\"upload\"; filename=\"{fn}\"\r\nContent-Type: image/png\r\n\r\n").encode()+open(path,"rb").read()+f"\r\n--{bnd}--\r\n".encode()
    fid=json.load(_op.open(urllib.request.Request(B+"/files",body,{"content-type":f"multipart/form-data; boundary={bnd}"},method="POST")))["id"]
    r=call("POST","/brands/1/screens",{"name":name,"file_id":fid,"tags":tags}); print(r["id"],name); return r["id"]
if __name__=="__main__":
    add(sys.argv[1],sys.argv[2],sys.argv[3].split(","))
