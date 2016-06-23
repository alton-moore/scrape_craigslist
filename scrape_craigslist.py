

# Look at craigslist pretty frequently to try to get new listings for sheds or whatever is passed in as an argument.


import sys
import os
import string
from StringIO import StringIO
import gzip
import time  # For the sleeping function; we will wait between some requests.
import MySQLdb

import urllib
import urllib2
from datetime import datetime, date
import re
import md5
import cookielib

import bs4
from bs4 import BeautifulSoup

import smtplib
from email.mime.text import MIMEText


# Some constants
CRAIGSLIST_URL         = 'http://austin.craigslist.org'  # This is the area to search.
SECONDS_BETWEEN_PASSES = 900
USER_AGENT             = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.7.8) Gecko/20050511'
COOKIE_FILENAME        = 'scrape_craigslist.dat'
FROM_ADDRESS           = 'scraper@alton-moore.net'
#TO_ADDRESS             = '9565815577@smtext.com'
TO_ADDRESS             = 'aomoore3@gmail.com'


def get_page_data(page_url):
    '''  Read the given page url, via a proxy if necessary, into a string.  '''
    #
    request = urllib2.Request(page_url)
    request.add_header('Accept-encoding', 'gzip')
    request.add_header('User-agent', USER_AGENT)
    #
    retry_count = 0;
    retry_limit = 25;
    while True:
        try:
            retry_count += 1
            if retry_count > retry_limit:
                print 'scrape_tehparadox.py: More than ', str(retry_limit), ' retries; exiting now.'
                sys.exit(1)
            response = urllib2.urlopen(request)
            break  # We got the desired page, so exit from the retry loop.
        except:
            print 'scrape_tehparadox.py: Problem getting web page; waiting 10 seconds before retrying.'
            time.sleep(10)
    #
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        f = gzip.GzipFile(fileobj=buf)
        data = f.read()
    return data


def search_for_term(database_connection):
    print 'Submitting search for', search_term, 'now.'
    #
    search_url = CRAIGSLIST_URL + '/search/sso?query=' + search_term + '&sort=date'
    print 'Submitting search:',search_url
    page_content = get_page_data(search_url)
    #
    soup = BeautifulSoup(page_content, 'html.parser')
    for div_item in soup.find_all('div'):
        starting_string = '<div class="content">'
        if str(div_item)[0:len(starting_string)] == starting_string:
            break
    #
    # At this point we should have the content class loaded in this div_item.  Search for paragraphs within this.
    soup = BeautifulSoup(str(div_item), 'html.parser')
    p_items = soup.find_all('p')
    print '<p> items found:',len(p_items)
    for p_item in p_items:
        #
#        print str(p_item)
#        print '-----'
        #
        # First get the posting ID, so we can see if it's on file already.  <p class="row" data-pid="4641436201">
        posting_id = p_item['data-pid']
        cur = database_connection.cursor(MySQLdb.cursors.DictCursor)
        sql_string = "SELECT * FROM craigslistresults WHERE posting_id = '" + posting_id + "'"
        cur.execute(sql_string)
        if len(cur.fetchall()) > 0:
            continue
        #
        # Parse out the other fields we want to save/send.
        soup2 = BeautifulSoup(str(p_item), 'html.parser')
        price = ''
        for a_item in soup2.find_all('a'):
            if 'class="price"' in str(a_item):  # Is the "price" <span> in here?
                price = a_item.text
                continue
            if len(a_item.text) > 0:  # This should happen on the 2nd <a> item.
                break
        url   = a_item['href'].encode('utf-8')
        title = a_item.text.encode('utf-8')
        #
        # Send the email.
        print 'Sending email to:',TO_ADDRESS
        message_body  = title
        message_body += ' -- ' + price + '\n\n'
        message_body += CRAIGSLIST_URL + url + '\n'
        msg = MIMEText(message_body)
        msg['Subject'] = 'From scraper'
        msg['From'] = FROM_ADDRESS
        msg['To']   = TO_ADDRESS
        s = smtplib.SMTP('localhost')  # Send message via local SMTP server; don't include envelope header.
        s.sendmail(FROM_ADDRESS, TO_ADDRESS, msg.as_string())
        s.quit()
        #
        # Write the result to the database.
        print 'Adding posting to database:', title, ' - ', price
        sql_string = "INSERT INTO craigslistresults "          + \
         " (posting_id,"                                       + \
           "price,"                                            + \
           "title,"                                            + \
           "url,"                                              + \
           "search_term) VALUE ('"
        sql_string += posting_id               + "','"
        sql_string += price                    + "','"
        try:
            sql_string += title.replace("'","\\'") + "','"
        except:
            sql_string += "(invalid title)"        + "','"
        sql_string += url.replace(  "'","\\'") + "','"
        sql_string += search_term              + "')"
        #print 'sql string: ', sql_string
        cur.execute(sql_string)
        #
    database_connection.commit()


if __name__ == '__main__':
    search_term   = sys.argv[1]  # The argument should be the thing we're looking for, like "shed".
    starting_hhmm = sys.argv[2]  # Time to start scraping and sending text messages.
    ending_hhmm   = sys.argv[3]  # Time to stop.

    database_connection = MySQLdb.connect('localhost', 'scrape', 'mooples', 'scraping')

    # Install proxy support.  Also only needs to be done once in the program.
    #proxy_url = "http://user:xxjf9@37.235.54.54:9999"
    #proxy_support = urllib2.ProxyHandler({'http': proxy_url})
    #opener = urllib2.build_opener(proxy_support)
    #urllib2.install_opener(opener)

    # Every 10 minutes, search for term on Austin craigslist, as long as we're inside of the time window.
    while True:
        #
        # First get the current HHMM and see if we're in the scraping window, so I don't get any text messages that wake me up.
        current_hhmm = time.strftime("%H%M")
        print 'Current HHMM is:', current_hhmm
        #
        if (current_hhmm >= starting_hhmm) and (current_hhmm <= ending_hhmm):
            print 'Starting a search pass.'
            search_for_term(database_connection)
        else:
            print 'Time outside of scraping window, so not searching now.'
            cur = database_connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute("SELECT NOW()")  # Hopefully this will keep the database connection alive.
        print 'Sleeping', str(SECONDS_BETWEEN_PASSES), 'before next pass.'
        time.sleep(SECONDS_BETWEEN_PASSES)


