Google App Engine project that initiates Google Voice calls scheduled in your Google Calendar.

Why do you need it? Let's assume that you need to call someone at a later time. Today, you can set up an event with reminder in your Google Calendar to do it. When you get the reminder you pick up the phone and start calling. With gvcallscheduler you don't need to do an extra step - Google Voice will call you and connect you and your party at the specified time. No more "forgotten" calls!

To schedule a GV call in your Google Calendar add the "GVCall=phonenumber" string to event's title or event's description and gvcallscheduler will start GV call at the event start time.

You must already have a Google Voice account for gvcallscheduler to work properly.

iPhone App "GVScheduler 1.0" is available in App Store - http://itunes.apple.com/us/app/gv-scheduler/id352720361?mt=8

## Installation Instructions ##

  1. Sign up for Google App Engine at http://code.google.com/appengine/.
  1. Create a new Python App. You can name it anything you want, but remember the name for later.
  1. Install the Google App Engine SDK from http://code.google.com/appengine/downloads.html
  1. Download the latest version of gvcallscheduler (to the right), or check it out from SVN (in the Source tab)
  1. Edit the file 'config'
    * change 'YOUR\_EMAIL' to your Google Voice email address
    * change 'YOUR\_PASSWORD to your Google password (use application-specific password if you enabled 2-step verification)
    * change 'FORWARDING\_NUMBER' to the phone number you you would like to ring
    * change 'PHONE\_TYPE' to the forwarding number phone type (2 - mobile, 7 - Gizmo)
  1. Edit the file 'app.yaml'
    * change YOUR\_GAE\_APP\_NAME to the name of your GAE App that you chose in step #2
  1. Publish the App to Appspot at http://code.google.com/appengine/docs/python/tools/uploadinganapp.html
  1. Visit your App URL (e.g. http://YOUR_GAE_APP_NAME.appspot.com/)
    * click on the displayed link to authorize access to your Google Calendar
    * subsequent visits to your App URL should display "GVScheduler is up and running - OK..."

Thanks to Chris Craft for detailed instructions available at http://edurls.org/3l