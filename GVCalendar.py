import gdata.alt.appengine
import gdata.calendar.service
import re, logging
import os
import atom.url
from rfc3339 import rfc3339
from datetime import datetime, timedelta
from conf import config
from googlevoice import *
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from collections import defaultdict
from gdata.auth import AuthSubToken

MEMKEY = 'GVC'

port = os.environ['SERVER_PORT']
if port and port != '80':
    HOST_NAME = '%s:%s' % (os.environ['SERVER_NAME'], port)
else:
    HOST_NAME = os.environ['SERVER_NAME']

def deletetokens():
	tokens = db.GqlQuery("SELECT * FROM Token ORDER BY date DESC")
	for token in tokens:
		token.delete()

class Token(db.Model):
	tokenstr = db.StringProperty()
	date = db.DateTimeProperty(auto_now_add=True)

class GVCalendar(webapp.RequestHandler):

	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.out.write('<html><head><title>GV Scheduler</title></head><body><div id="main">')
		self.cal_client = gdata.calendar.service.CalendarService()
		# Tell the client that we are running in single user mode, and it should not
		# automatically try to associate the token with the current user then store
		# it in the datastore.
		gdata.alt.appengine.run_on_appengine(self.cal_client, store_tokens=False, single_user_mode=True)
		# Load processed events to avoid multiple calls for the same event
		self.processed_events = memcache.get(MEMKEY)
		if self.processed_events is None:
			self.processed_events = defaultdict(set)
		#logging.debug('Loaded memcache: %s' % str(self.processed_events))
       	# Find an AuthSub token in the current URL if we arrived at this page from an AuthSub redirect
		session_token = None
		auth_token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)
		if auth_token:
			# Upgrade the single-use AuthSub token to a multi-use session token.
			session_token = self.cal_client.upgrade_to_session_token(auth_token)
            # Store the token in the datastore
			if session_token:
				tkn = Token()
				tkn.tokenstr = session_token.get_token_string()
				tkn.put()
				#logging.debug('Storing session token: %s' % session_token)
				self.response.out.write('</div></body></html>')
				self.redirect("/")
		else:
			# Token stored in DB?
			tknn = (db.GqlQuery("SELECT * FROM Token ORDER BY date DESC LIMIT 1")).get()
			if tknn:
				session_token = AuthSubToken()
				session_token.set_token_string(tknn.tokenstr)				
				#logging.debug('Read session token from DB: %s' % session_token)
		#Is this app authorized to access Google Calendar?
		feed_url = 'http://www.google.com/calendar/feeds/'
		if not session_token:
			# Tell the user that they need to login to authorize this app by logging in at the following URL.
			next = atom.url.Url('http', HOST_NAME, path='/', params={'feed_url': feed_url})
			auth_sub_url = self.cal_client.GenerateAuthSubURL(next, feed_url, secure=False, session=True)
			self.response.out.write('<a href="%s">Please click here to authorize GVScheduler to access your Google Calendar</a>' % (auth_sub_url))
			logging.error('Please visit your app URL (e.g. http://YOUR_GAE_APP_NAME.appspot.com/) to authorize access to your Google Calendar')
		else:
			#logging.debug('Found session_token: %s' % session_token)
			self.cal_client.SetAuthSubToken(session_token)
			self.response.out.write('GVScheduler is up and running - <font color=green>OK</font>...')
			feed = self.GetEventsFromCalendar()
			if feed:
				if feed.entry:
					for i, an_event in zip(xrange(len(feed.entry)), feed.entry):
						# Look in Title and Content of the event...
						combstring = an_event.title.text if an_event.title.text is not None else ''
						combstring += ('\n' + an_event.content.text) if an_event.content.text is not None else '' 
						kd = self.ParseString(combstring)
						# Test if call needs to be placed. Entry must have "GVCall=number" in Title or in Content
						if ("gvcall" in kd):
							pn = self.FormatPhoneNumber(kd['gvcall'])
							starttime = an_event.when[0].start_time
							# Check if the call for this event was already placed
							if (not self.processed_events[starttime]) or (pn not in self.processed_events[starttime]):
								if ("gvringnumber" in kd):
									rn = self.FormatPhoneNumber(kd['gvringnumber'])
								else:
									rn = config.forwardingNumber
								if ("gvringtype" in kd):
									rt = kd['gvringtype']
								else:
									rt = config.phoneType
								logging.info('Event: %s, Calling: %s, Ringing: %s (Type: %s)' % (an_event.title.text, pn, rn, rt))
								self.GVPlaceCall(pn, rn, rt)
								self.processed_events[starttime].add(pn)
								#logging.debug('Adding to memcache: [%s] = (%s)' % (starttime, pn))
							#else:
							#	logging.debug('Skipping processed event: [%s] = (%s)' % (starttime, pn))
					memcache.set(MEMKEY, self.processed_events)
				else:
					# No events fetched, clear the cache
					memcache.flush_all()
					#logging.debug('Deleting memcache...')
		self.response.out.write('</div></body></html>')		

	def GetEventsFromCalendar(self):
		# Query calendar for events from: now() to: (now() + 1 min) 
		query = gdata.calendar.service.CalendarEventQuery('default', 'private', 'full')
		dt = datetime.utcnow()
		query.start_min = rfc3339(dt, utc=True)
		query.start_max = rfc3339(dt + timedelta(minutes=1), utc=True)
		query.ctz = 'UTC'
		feed = None
		try:
			feed = self.cal_client.CalendarQuery(query)
			return feed
		except gdata.service.RequestError, request_error:
			# If fetching fails, then AuthToken is invalid - delete it
			if request_error[0]['status'] == 401:
				deletetokens()
				logging.info('Deleted invalid AuthSub Session token')
				self.redirect("/")
			else:
				logging.error('Error: %s ' % (str(request_error[0])))
			return None
			
	def GVPlaceCall(self, outnumber, ringnumber, ringnumbertype):
		gv = GoogleVoiceLogin(config.email, config.password)
		if not gv.logged_in:
			logging.error("Could not log in to GV with provided credentials as %s, Status=%d, Error=%s" % (config.email, gv.post_response.status_code, gv.post_response.headers.get('Error')))
			# Fine Captcha token value
			key = re.search('https://www.google.com/accounts/Captcha\?ctoken=(.*?)"', gv.post_response.content)
			if key:
				logging.error("Captcha required, please visit 'https://www.google.com/accounts/DisplayUnlockCaptcha' to unlock Captcha")
		else:
			number_dialer = NumberDialer(gv.opener, gv.key)
			number_dialer.forwarding_number = ringnumber
			number_dialer.forwarding_number_type = ringnumbertype
			number_dialer.place_call(outnumber)
		if not number_dialer.response:
			logging.error("Call Failed, response: %s" % number_dialer.response)	
		GoogleVoiceLogout();

	def ParseString(self, line):
	 	# Parse string for "Key=Value" tokens, one token per line
		return dict([(match.group(1).lower(), match.group(2)) 
			for match in re.finditer('^[ \t]*([^=\n]+) *= *(.*)$', line, re.M)]) if line is not None else {}
		
	def FormatPhoneNumber(self, innumber):
		pn = re.sub("[^0-9+]", "", innumber)
		#add 1 if it's 10 digits without '+'
		if (len(pn) == 10) and (pn[0] != "1") and (pn[0] != "+"):
		    pn = '1' + pn
		#add "+" as 1st char
		if (pn[0] != "+"): 
			pn = '+' + pn	
		return pn
			
class TestGVLogin(GVCalendar):
	def get(self):
		email = self.request.get('email')
		password = self.request.get('password')
		if email == '':
			email = config.email
		if password == '':
			password = config.password
		gv = GoogleVoiceLogin(email, password)
		self.response.headers['Content-Type'] = 'text/html'
		self.response.out.write('<html><head><title>GV Scheduler</title></head><body><div id="main">')
		if not gv.logged_in:
			self.response.out.write('Google Voice Login as "%s" - <font color=red>Failed</font><BR><HR>' % email)
			self.response.out.write("Status=%d<BR>" % gv.post_response.status_code)
			self.response.out.write("Error=%s<BR><HR>" % gv.post_response.headers.get('Error'))	
			# Fine Captcha token value
			key = re.search('https://www.google.com/accounts/Captcha\?ctoken=(.*?)"', gv.post_response.content)
			if key:
				self.response.out.write("Captcha required - token:%s<BR><BR>" % key.group(1))
				self.response.out.write("<A HREF='https://www.google.com/accounts/DisplayUnlockCaptcha'>Please click here to unlock Captcha</A>")
				#self.response.out.write(gv.post_response.content)
		else:
			self.response.out.write('Google Voice Login as "%s" - <font color=green>OK</font>' % email)
		self.response.out.write('</div></body></html>')
		GoogleVoiceLogout();

		
application = webapp.WSGIApplication([('/', GVCalendar),
									  ('/testgvlogin', TestGVLogin)],
									 debug=True)

def main():
	run_wsgi_app(application)
	

if __name__ == "__main__":
	main()

