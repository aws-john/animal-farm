# Animal Farm!
# Based on: https://www.pyimagesearch.com/2015/09/14/ball-tracking-with-opencv/

# import the necessary packages
from collections import deque
from imutils.video import VideoStream
import numpy as np
import cv2
import imutils
import time
import math
import json
import boto3
import awscamdldt as awscam
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient

clientId = 'DeepLens'
host = 'xxx-ats.iot.us-west-2.amazonaws.com'
port = 443
rootCAPath = 'AmazonRootCA1.pem'
thingName = 'animals'

# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient(clientId, useWebsocket=True)
myAWSIoTMQTTShadowClient.configureEndpoint(host, port)
myAWSIoTMQTTShadowClient.configureCredentials(rootCAPath)

# AWSIoTMQTTShadowClient configuration
myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect to AWS IoT
myAWSIoTMQTTShadowClient.connect()

# Create a deviceShadow with persistent subscription
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName(thingName, True)

# Colours to use, with Hue value
COLOURS = [
	{'Colour':'Green', 'Hue':40},
	{'Colour':'Blue',  'Hue':100},
	{'Colour':'Orange','Hue':15},
	{'Colour':'Pink',  'Hue':165},
]

# Frame timer
last_time = time.time()

# Keep looping
while True:
	# grab the current frame
	ret, frame = awscam.getLastFrame()

	# resize the frame, blur it, and convert it to the HSV color space
	frame = imutils.resize(frame, width=800)
	frame = cv2.flip(frame, -1)
	original_frame = frame.copy()
	blurred = cv2.GaussianBlur(frame, (11, 11), 0)
	hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
	
	# Initialize output
	output = {'animals':[]}
	
	# Loop through the colours
	for colour in COLOURS:

		# construct a mask for the color, then perform
		# a series of dilations and erosions to remove any small
		# blobs left in the mask
		if colour['Colour'] == 'Orange':
			mask = cv2.inRange(hsv, (colour['Hue']-15, 80, 140), (colour['Hue']+15, 255, 255)) # 80, 120
		else:
			mask = cv2.inRange(hsv, (colour['Hue']-15, 80, 100), (colour['Hue']+15, 255, 255)) # 80, 120
		mask = cv2.erode(mask, None, iterations=2)
		mask = cv2.dilate(mask, None, iterations=2)

		# Show each colour (Optional)
		if False:
			original = original_frame.copy()
			show = cv2.bitwise_and(original, original, mask=mask)
			cv2.imshow(colour['Colour'], show)

		# find contours in the mask and initialize the current
		# (x, y) center of the shape
		contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
		center = None
		
		# only proceed if at least one contour was found
		if len(contours) > 0:
			# find the largest contour in the mask, then use
			# it to compute the centre
			c = max(contours, key=cv2.contourArea)
			((x, y), radius) = cv2.minEnclosingCircle(c)
			M = cv2.moments(c)
			center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

			# only proceed if the radius meets a minimum size
			if radius > 10:

				# Draw outline and center
				cv2.circle(frame, center, 5, (0, 0, 255), -1)
				cv2.drawContours(
					image=frame,
					contours=[c],
					contourIdx=0,
					color=(0,255,0),
					thickness=3
					)

				# Find all children contours to locate triangle to determine angle
				child_contours = []
				try:
					parent_index = contours.index(c)
					child_contours = [contours[i] for i, h in enumerate(hierarchy[0]) if h[3] == parent_index]
				except ValueError:
					print ('Value error, len(c)=', len(c))
				

				if len(child_contours) > 0:
					# find the largest contour
					corner = max(child_contours, key=cv2.contourArea)
					((x, y), radius) = cv2.minEnclosingCircle(corner)
					M = cv2.moments(corner)
					corner_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

					# Draw outline and center
					cv2.circle(frame, corner_center, 5, (0, 255, 255), -1)

					# Draw line from center to triangle
					cv2.line(frame, center, corner_center, (255, 0, 255), 3)

					# Prepare data
					radians = math.atan2(center[1]-corner_center[1], center[0]-corner_center[0])
					output['animals'].append([colour['Colour'], center[0], center[1], radians])


	# Send data to IoT
	if output['animals']:
		payload = {"state":{"reported":output}}
		str_payload = json.dumps(payload)
		deviceShadowHandler.shadowUpdate(str_payload, None, 5)
		print(time.time() - last_time)
		last_time = time.time()
		
	# Show the frame on the screen
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF

	# if the 'q' key is pressed, stop the loop
	if key == ord("q"):
		break

# Finished!
vs.stop()
cv2.destroyAllWindows()
