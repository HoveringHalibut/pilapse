from flask import Flask, request, render_template, redirect, url_for, send_from_directory, current_app, Response
from flask_paginate import Pagination, get_page_args

from functools import total_ordering
from itertools import zip_longest

import re
import colorsys
import time
import datetime
import math
import threading
import os

import blinkt

app = Flask(__name__)

shortDateOrder = {
  's': 1,
  'm': 2,
  'h': 3,
  'd': 4,
  'w': 5,
  'M': 6,
  'y': 7
}

bolLapseRunning = False

secRainbow = 5
waitSeconds = 5
curPicture = 1
seriesName = 'default'

rePath = re.compile("[^0-9]*([0-9]*)([smhdwMy]).*")

@app.before_first_request
def initialize():
  if not os.path.exists('./images'):
    os.mkdir('./images')

def grouper(iterable, n, fillvalue=None):
  args = [iter(iterable)] * n
  return zip_longest(*args, fillvalue=fillvalue)

def rainbow(runSeconds: int = 5, clear: bool = True, decreaseBrightness: bool = False):
  spacing = 360.0 / 8.0
  hue = 0

  blinkt.set_clear_on_exit()

  start_time = datetime.datetime.now()

  tSeconds = (datetime.datetime.now() - start_time).total_seconds()

  while (tSeconds < runSeconds) :
    hue = int(time.time() * 100) % 360

    for x in range(blinkt.NUM_PIXELS):
      offset = x * spacing
      h = ((hue + offset) % 360) / 360.0
      r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(h, 1.0, 1.0)]
      blinkt.set_pixel(x, r, g, b)

    brightness = math.ceil((tSeconds/runSeconds)*10)/10

    if(decreaseBrightness):
      brightness = 1 - brightness

    blinkt.set_brightness(brightness)

    blinkt.show()
    time.sleep(0.005)
    tSeconds = (datetime.datetime.now() - start_time).total_seconds()

  if clear:
    blinkt.clear()
    blinkt.show()

def colorrotate(runSeconds: int = 5, clear: bool = True, decreaseBrightness: bool = False):
  hue = 0

  blinkt.set_clear_on_exit()

  start_time = datetime.datetime.now()

  tSeconds = (datetime.datetime.now() - start_time).total_seconds()

  while (tSeconds < runSeconds) :
    brightness = math.ceil((tSeconds/runSeconds)*10)/10

    if(decreaseBrightness):
      brightness = 1 - brightness

    hue = int(time.time() * 100) % 360
    h = (hue % 360) / 360.0
    r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(h, 1.0, 1.0)]
    blinkt.set_all(r, g, b, brightness)

    blinkt.show()
    time.sleep(0.005)
    tSeconds = (datetime.datetime.now() - start_time).total_seconds()

  if clear:
    blinkt.clear()
    blinkt.show()

def takepicture(imageName: str):
  with picamera.PiCamera() as camera:
    camera.resolution = (1920, 1080)
    time.sleep(1) # Camera warm-up time
    filename = 'images/%s.jpg' % imageName
    camera.capture(filename)

def timeLapse():
  global curPicture, waitSeconds, seriesName

  if not os.path.exists('./images/%s' % seriesName):
    os.mkdir('./images/%s' % seriesName)

  with picamera.PiCamera() as camera:
    camera.resolution = (1920, 1080)
    time.sleep(1)

    while bolLapseRunning:
      filename = 'images/%s/%s.jpg' % (seriesName, curPicture)
      camera.capture(filename)
      curPicture += 1
      time.sleep(waitSeconds)

def gen(camera):
  while True:
    frame = camera.get_frame()
    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
  return Response(gen(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/preview')
def imagepreview():
  return render_template('preview.html')

@app.route('/imagelist')
def imagelist():

  search = False
  q = request.args.get('q')
  if q:
      search = True

  images = []

  it = os.scandir('./images/')
  for entry in it:
      if not entry.name.startswith('.') and entry.name.endswith('.jpg') and entry.is_file():
          images.append(entry.name)

  images.sort()

  page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
  print(per_page)
  pagination = Pagination(
    page=page,
    total=len(images),
    search=search,
    record_name='images',
    per_page=per_page,
    format_total=True,
    format_number=True,
    css_framework=current_app.config.get('CSS_FRAMEWORK', 'sm'),
    link_size=current_app.config.get('LINK_SIZE', 'sm'),
    alignment=current_app.config.get('LINK_ALIGNMENT', ''),
    show_single_page=current_app.config.get('SHOW_SINGLE_PAGE', 'sm')
    )

  pageimages = grouper(images[offset:offset+per_page], 3)

  templateData = {
    'pagination' : pagination,
    'images': pageimages,
    'page' : page,
    'per_page' : per_page
  }

  return render_template('imagelist.html', **templateData)

@app.route('/images/<path:path>')
def send_image(path):
    return send_from_directory('images', path)

@app.route('/', methods=['GET', 'POST'])
def index():

  now = datetime.datetime.now()
  timeString = now.strftime("%Y-%m-%d %H:%M")
  global secRainbow, bolLapseRunning, seriesName, waitSeconds, seriesName

  if request.method == 'POST':
    secRainbow = int(request.form['secRainbow'])
    waitSeconds = int(request.form['waitSeconds'])
    seriesName = request.form['seriesName']
    if request.form['submit'] == 'Rainbow':
      t = threading.Thread(target=rainbow, args=(secRainbow,))
      t.start()
    elif request.form['submit'] == 'ColorRotate':
      t = threading.Thread(target=colorrotate, args=(secRainbow,))
      t.start()
    elif request.form['submit'] == 'StartTimeLapse':
      if not bolLapseRunning:
        bolLapseRunning = True
        t = threading.Thread(target=timeLapse)
        t.start()
    elif request.form['submit'] == 'StopTimeLapse':
      bolLapseRunning = False
    elif request.form['submit'] == 'Take Picture':
      if not bolLapseRunning:
        takepicture('test')

  templateData = {
    'time': timeString,
    'startLapseEnabled': "disabled" if bolLapseRunning else "",
    'stopLapseEnabled': "disabled" if not bolLapseRunning else "",
    'secRainbow': secRainbow,
    'waitSeconds': waitSeconds,
    'seriesName': seriesName
  }

  return render_template('index.html', **templateData)

# Clear blinkt in case it was left on after a unexpected shutdown or crash
blinkt.clear()
blinkt.show()

if __name__ == '__main__':
  if(app.config['ENV']!='development'):
    import picamera
    from camera_pi import Camera
    app.run(port=80,host="0.0.0.0")
  else:
    app.run(port=5000)