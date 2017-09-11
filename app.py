import os, time, boto, uuid, datetime, redis
r = redis.Redis(host='redis-17715.c14.us-east-1-3.ec2.cloud.redislabs.com', port='17715', password='XXXX')
#r = redis.Redis(host='127.0.0.1', port='6379')
from flask import Flask, render_template, redirect, request, url_for, make_response
from werkzeug import secure_filename

ecs_access_key_id = 'XXXX@ecstestdrive.emc.com'  
ecs_secret_key = 'XXXX'

session = boto.connect_s3(ecs_access_key_id, ecs_secret_key, host='object.ecstestdrive.com')  
bname = 'foodblog'
b = session.get_bucket(bname)
print "Bucket is: " + str(b)

app = Flask(__name__)
app.config['ALLOWED_EXTENSIONS'] = set(['jpg', 'jpeg', 'JPG', 'JPEG'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def foodblog():
    resp = make_response(render_template('main.html'))
    return resp
                
@app.route('/blogentry')
def blogentry():
    resp = make_response(render_template('entryform.html'))
    return resp


@app.route('/entryadded', methods=['POST'])
def entryadded():
    # first, only proceed if the photo is legit 
    myfile = request.files['file']
    if myfile and allowed_file(myfile.filename):

        # deal with the photo first
        ## Make the file name safe, remove unsupported chars
        file_name = secure_filename(myfile.filename)
        ## Apple iPhones use just "image" as the filename when uploading
        ## So need to come up with a unique name
        ## In this case we prepend epoch time in milliseconds to file name
        unique_name = str(int(time.time()*1000)) + "-" + file_name
        ## Now we save the file in the uploads folder
        myfile.save(os.path.join("uploads", unique_name))
        # Upload the file to ECS
        print "Uploading " + unique_name + " to ECS"
        k = b.new_key(unique_name)
        k.set_contents_from_filename("uploads/" + unique_name)
        k.set_acl('public-read')
        # Finally remove the file from our container. We don't want to fill it up ;-)
        os.remove("uploads/" + unique_name)

        # now deal with the rest
        counter = r.incr('record')
        date = request.form['date']
        mealtype = request.form['mealtype']
        calories = request.form['calories']
        description = request.form['description']
        entrynum = 'entry-' + str(counter)
        # create a value based on the date the user adds when they create the blog entry
        moddate = date.split("-")
        entryscore = (datetime.datetime(int(moddate[0]),int(moddate[1]),int(moddate[2]),0,0) - datetime.datetime(1970,1,1)).total_seconds()
        # create a sorted set, which stores the date value along with each entry number
        r.zadd('entryzset',entrynum,entryscore)
        # now store the blog entry in a hash, with the key set to the blog entry number
        r.hmset(entrynum,{'date':date,'mealtype':mealtype,'calories':int(calories),'description':description,'photo':unique_name})

        resp = make_response(render_template('entryadded.html'))
        return resp

    else: return """<h3> - Your photo name was invalid, nothing was done - </h3> <a href="/"><h3>Back to food blog main page</h3></a>"""

@app.route('/viewblog')
def viewblog():
    entries = []
    calories = 0
    string = str(r.zrange('entryzset',0,-1))
    records = string.split(",")
    dump = """<table class="table table-striped">
    <tbody>"""

    # grab the list of entry numbers from the sorted set and store them in a list called entries,
    # they will come out in order of the date value set with each
    for record in records:
        rawentry = record.split("'")
        entries.append(rawentry[1])

    # now grab each blog entry from the hash which corresponds to the entry number,
    # they will be displayed in chronological format,
    # -- regardless of the date/time on which they were added to the blog --
    for entry in entries:
        meal = r.hmget(entry,{'date','mealtype','calories','description','photo'})
##        entrydate = r.hget(entry,{'date'})
##        entrytype = r.hget(entry,{'mealtype'})
##        entrycal = r.hget(entry,{'calories'})
##        entrydesc = r.hget(entry,{'description'})
##        entryphoto = r.hget(entry,{'photo'})
##        print entrydate
##        print entrytype
##        print entrycal
##        print entrydesc
##        print entryphoto
        
        print meal[0]
        print meal[4]
        print meal[2]
        print meal[3]
        print meal[1]
        print "--next"
##        photoname1 = str(meal[1]).split(",")
##        photoname2 = photoname1[1].split(">")
##        photoname = photoname2[0]
##        print meal[0]
##        print meal[4]
##        print meal[2]
##        print meal[3]
##        print photoname
##        print "--next"
        
        if len(str(meal[2])) > 0:
            calories = calories + int(meal[2])
            dump = dump + """
                        <tr style="width: 100%">
                            <td style="width: 70%"><br>Date: {}<br>Meal Type: {}<br>Calories: {}<br>Description: {}<br></td>
                            <td><img src="http://131396950294169841.public.ecstestdrive.com/foodblog/{}" width=200 class="img-thumbnail"></td></tr>
                        """.format(str(meal[0]),str(meal[1]),str(meal[2]),str(meal[3]),str(meal[4]))
        else:
            dump = dump + """
                        <tr style="width: 100%">
                            <td style="width: 70%"><br>Date: {}<br>Meal Type: {}<br>Calories: 0<br>Description: {}<br></td>
                            <td><img src="http://131396950294169841.public.ecstestdrive.com/foodblog/{}" width=200 class="img-thumbnail"></td></tr>
                        """.format(str(meal[0]),str(meal[1]),str(meal[3]),str(meal[4]))

    dump = dump + """</table>"""
    resp = make_response(render_template('viewblog.html').format(dump,calories))
    return resp


# this is just used to clean the redis database and delete photos in the ECS bucket
@app.route('/redisclean')
def redisclean():

    entries = []
    string = str(r.zrange('entryzset',0,-1))
    records = string.split(",")
    for record in records:
        rawentry = record.split("'")
        entries.append(rawentry[1])
    for entry in entries:
        r.hdel(entry,{'date','mealtype','calories','description'})

    r.zremrangebyrank('entryzset',0,-1)

    for x in b.list():
        b.delete_key(x.key)

    return """
    <link rel="stylesheet" href=href="/css/theme.css">
    <h3> - Redis keys have been cleaned, and ECS bucket emptied! - </h3>
    <a href="/"><h3>Back to food blog main page</h3></a>
    """

if __name__ == "__main__":
    app.run(debug=False,host='0.0.0.0', port=int(os.getenv('PORT', '5000')))

