import urllib, urllib2, Cookie
from google.appengine.api import urlfetch
import csv
import sys
import re

class URLOpener:
  def __init__(self):
      self.cookie = Cookie.SimpleCookie()
      self.auth = None
    
  def open(self, url, data = None):
	if data is None:
	    method = urlfetch.GET
	else:
	    method = urlfetch.POST
    
	while url is not None:
	    response = urlfetch.fetch(url=url,
	                    payload=data,
	                    method=method,
	                    headers=self._getHeaders(self.cookie),
	                    allow_truncated=True,
	                    follow_redirects=False,
	                    deadline=10
	                    )
	    data = None # Next request will be a get, so no need to send the data again. 
	    method = urlfetch.GET
	    self.cookie.load(response.headers.get('set-cookie', '')) # Load the cookies from the response
	    url = response.headers.get('location')

	return response
        
  def _getHeaders(self, cookie):
      headers = {
                 'Host' : 'www.google.com',
                 'User-Agent' : 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.2) Gecko/20090729 Firefox/3.5.2 (.NET CLR 3.5.30729)',
                 'Cookie' : self._makeCookieHeader(cookie)
                  }
      if self.auth is not None:
           headers['Authorization'] = 'GoogleLogin auth=%s' % self.auth
      return headers

  def _makeCookieHeader(self, cookie):
      cookieHeader = ""
      for value in cookie.values():
          cookieHeader += "%s=%s; " % (value.key, value.value)
      return cookieHeader

class GoogleVoiceLogin:
	def __init__(self, email, password):
		# Set up our opener
		self.opener = URLOpener()
		
		# Define URLs
		login_page_url = 'https://www.google.com/accounts/ClientLogin'
		gv_home_page_url = 'https://www.google.com/voice/#inbox'
		
		# Set up login credentials
		login_params = urllib.urlencode( { 
			'Email' : email,
			'Passwd' : password,
			'accountType' : 'HOSTED_OR_GOOGLE',
			'service': 'grandcentral',
			'source': 'GVCalendar'
		})

		# Login
		self.logged_in = False
		self.post_response = self.opener.open(login_page_url, login_params)
		if self.post_response.status_code == 200:
			
			# Find AUTH value
			auth = re.search('Auth=(.+)\n', self.post_response.content, re.IGNORECASE)
			if auth:
				self.opener.auth = auth.group(1)
				
				# Open GV home page
				self.gv_home_page_contents = self.opener.open(gv_home_page_url).content

				# Fine _rnr_se value
				key = re.search('name="_rnr_se".*?value="(.*?)"', self.gv_home_page_contents)

				if key:
					self.logged_in = True
					self.key = key.group(1)
				

class GoogleVoiceLogout:			
	def __init__(self):
		# Set up our opener
		self.opener = URLOpener()
		# Log out
		self.opener.open('https://www.google.com/voice/account/signout')

		
class TextSender():
	def __init__(self, opener, key):
		self.opener = opener
		self.key = key
		self.sms_url = 'https://www.google.com/voice/sms/send/'
		self.text = ''
		
	def send_text(self, phone_number):
		sms_params = urllib.urlencode({
			'_rnr_se': self.key,
			'phoneNumber': phone_number, 
			'text': self.text
		})
		# Send the text, display status message  
		self.response  = self.opener.open(self.sms_url, sms_params).content

class NumberDialer():
	def __init__(self, opener, key):
		self.opener = opener
		self.key = key
		self.call_url = 'https://www.google.com/voice/call/connect/'
		self.forwarding_number = None
		self.forwarding_number_type = 0
		
	def place_call(self, number):
		call_params = urllib.urlencode({
			'outgoingNumber' : number,
			'forwardingNumber' : self.forwarding_number,
			'phoneType': self.forwarding_number_type,
			'subscriberNumber' : 'undefined',
			'remember' : '0',
			'_rnr_se': self.key
			})

		# Send the text, display status message  
		self.response  = self.opener.open(self.call_url, call_params).content

