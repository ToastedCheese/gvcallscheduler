import gdata.alt.appengine
import gdata.calendar.service
import re, logging
from rfc3339 import rfc3339
from datetime import datetime, timedelta
from conf import config
from googlevoice import *
from google.appengine.api import memcache
from collections import defaultdict

MEMKEY = 'GVC'

class GVCalendar:

	def __init__(self, email, password):
	   	"""Creates a CalendarService"""
   
	   	self.cal_client = gdata.calendar.service.CalendarService()
		# Tell the client that we are running in single user mode, and it should not
		# automatically try to associate the token with the current user then store
		# it in the datastore.
		gdata.alt.appengine.run_on_appengine(self.cal_client, store_tokens=False, single_user_mode=True)
	   	self.cal_client.email = email
	   	self.cal_client.password = password
	   	self.cal_client.source = 'Google-Calendar_VoiceScheduler-1.0'
	   	self.cal_client.ProgrammaticLogin()
		# Load processed events to avoid multiple calls for the same event
		self.processed_events = memcache.get(MEMKEY)
		if self.processed_events is None:
			self.processed_events = defaultdict(set)
		#logging.debug('Loaded memcache: %s' % str(self.processed_events))

	def GetEventsFromCalendar(self):
		# Query calendar for events from: now() to: (now() + 1 min) 
		query = gdata.calendar.service.CalendarEventQuery('default', 'private', 'full')
		dt = datetime.utcnow()
		query.start_min = rfc3339(dt, utc=True)
		query.start_max = rfc3339(dt + timedelta(minutes=1), utc=True)
		query.ctz = 'UTC'
		return self.cal_client.CalendarQuery(query)
			
	def GVPlaceCall(self, outnumber):
		gv = GoogleVoiceLogin(config.email, config.password)
		if not gv.logged_in:
			logging.error("Could not log in to GV with provided credentials")
			sys.exit(1)
		number_dialer = NumberDialer(gv.opener, gv.key)
		number_dialer.forwarding_number = config.forwardingNumber
		number_dialer.forwarding_number_type = config.phoneType
		number_dialer.place_call(outnumber)
		if not number_dialer.response:
			logging.error("Call Failed, response: %s" % number_dialer.response)	

	def ParseString(self, line):
	 	# Parse string for "Key=Value" tokens, one token per line
		return dict([(match.group(1).lower(), match.group(2)) 
			for match in re.finditer('^[ \t]*([^=\n]+) *= *(.*)$', line, re.M)]) if line is not None else {}
		
	def FormatPhoneNumber(self, innumber):
		pn = re.sub("[^0-9]", "", innumber)
		#add 1st char if it's not 1
		if (len(pn) < 11) and (pn[0] != "1"):
		    pn = '1' + pn
		#add "+" as 1st char 
		pn = '+' + pn	
		return pn
		
def main():
	gvc = GVCalendar(config.email, config.password)
	feed = gvc.GetEventsFromCalendar()
	if feed.entry:
		for i, an_event in zip(xrange(len(feed.entry)), feed.entry):
			# Look in Title and Content of the event...
			combstring = an_event.title.text if an_event.title.text is not None else ''
			combstring += ('\n' + an_event.content.text) if an_event.content.text is not None else '' 
			kd = gvc.ParseString(combstring)
			# Test if call needs to be placed. Entry must have "GVCall=number" in Title or in Content
			if ("gvcall" in kd):
				pn = gvc.FormatPhoneNumber(kd['gvcall'])
				starttime = an_event.when[0].start_time
				# Check if the call for this event was already placed
				if (not gvc.processed_events[starttime]) or (pn not in gvc.processed_events[starttime]):
					gvc.GVPlaceCall(pn)
					logging.info('Event: %s, Calling: %s' % (an_event.title.text, pn))
					gvc.processed_events[starttime].add(pn)
					#logging.debug('Adding to memcache: [%s] = (%s)' % (starttime, pn))
				#else:
				#	logging.debug('Skipping processed event: [%s] = (%s)' % (starttime, pn))
		memcache.set(MEMKEY, gvc.processed_events)
	else:
		# No events fetched, clear the cache
		memcache.flush_all()
		#logging.debug('Deleting memcache...')

if __name__ == "__main__":
	main()

