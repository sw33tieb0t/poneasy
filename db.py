from google.appengine.api.users import User
from google.appengine.ext.db import metadata
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext.db.polymodel import PolyModel
from datetime import datetime
import webapp2
import logging
import json
import datetime
import time
import re

class console():
	def log(self, stuff):
		logging.warn(stuff)
console = console()

def ts(d):
	return long((d - datetime.datetime.utcfromtimestamp(0)).total_seconds()*1000)

def dt(n):
	return datetime.datetime.utcfromtimestamp(float(n)*0.001)

def totimestamp(d):
	return '(new Date({0:d}))'.format(ts(d))

def fromtimestamp(s):
	if re.match('^\(new Date\(\d+\)\)$',s):
		return dt(re.sub('\D+','',s))
	return s

def apply(a, b):
	if type(a) is unicode:
		a = fromtimestamp(a)
		try:
			a = json.loads(a)
		except:
			pass
	if type(b) is unicode:
		b = fromtimestamp(b)
		try:
			b = json.loads(b)
		except:
			pass
	if type(a) is dict and type(b) is dict:
		for key in b:
			if key in a:
				a[key] = apply(a, b)
				if a[key] == None:
					del a[key]
			else:
				a[key] = b[key]
	else:
		return b
	return a

class JsonProperty(db.TextProperty):
	def validate(self, value):
		return value
	def get_value_for_datastore(self, model_instance):
		result = super(JsonProperty, self).get_value_for_datastore(model_instance)
		result = json.dumps(result)
		return db.Text(result)
	def make_value_from_datastore(self, value):
		try:
			value = json.loads(str(value))
		except:
			pass
		return super(JsonProperty, self).make_value_from_datastore(value)
	def apply(self,json):
		return apply(self,json)

class actions(webapp2.RequestHandler):
	def __init__(self, request, response):
		super(self.__class__, self).__init__(request, response)
		self.result = { 'warnings': [], 'errors': [], 'data': [] }
		self.admin = users.is_current_user_admin()
		
		self.user = None
		self.admin = False
		self.client = None
		try:
			self.body = json.loads(self.request.body)
			self.auth()
		except:
			self.body = None
			self.error('500: Request Body is not valid json.')
	def post(self):
		console.log(self.body)
		console.log(self.client)
		if not self.client is None:
			if 'updates' in self.body:
				keys = []
				for key in self.body['updates']:
					try:
						keys.append(db.Key(key))
					except:
						pass
				entities = Entity.get(keys)
				for entity in entities:
					entity.execute(self.body['updates'][str(entity.key())])
				db.put(entities)
				for entity in Entity.gql('updated > :updated', updated = self.client.updated):
					self.data(entity)
			if 'creates' in self.body:
				entities = []
				for name in self.body['creates']:
					kind = db.class_for_kind(name)
					for data in self.body['create'][name]:
						entity = kind(data = data)
						entities.append(entity)
				db.put(entities)
				for entity in entities:
					self.data(entity)
			self.client.updated = datetime.utcnow()
			self.client.put()
			self.data(self.client)
		return self.out()
		
		'''
		kinds = {}
		entities = []
		updates = {}
		nokeys = []
		keys = []
		if not self.body or not 'data' in self.body:
			self.error('500: body or data of ajax call is missing or invalid.')
			return self.out()
		for update in self.body['data']:
			if not '_kind' in update:
				update['_kind'] = 'Entity'
			try:
				kinds[update['_kind']] = db.class_for_kind(update['_kind'])
			except:
				self.error('500: Invalid Kind: ' + str(update['_kind']))
			if not '_key' in update:
				ent = kinds[update['_kind']]()
				ent._data = update
				entities.append(ent)
			else:
				try:
					key = db.Key(str(update['_key']))
					keys.append(key)
					updates[str(key)] = update
				except:
					self.error('500: Invalid Database Key Format: ' + str(update['_key']))
		db.put(entities)
		for kind in kinds:
			entities += kinds[kind].get(keys)
		for entity in entities:
			entity._server = self
			if str(entity.key()) in updates:
				entity._data = updates[str(entity.key())]
			for key in entity._data:
				if type(entity._data[key]) is unicode:
					entity._data[key] = fromtimestamp(entity._data[key])
			if not '_calls' in entity._data or not type(entity._data['_calls']) is list:
				entity._data['_calls'] = []
			if not 'update' in entity._data['_calls']:
				entity._data['_calls'].append('update')
			entitydir = dir(entity)
			for call in entity._data['_calls']:
				if type(call) is unicode or type(call) is str:
					calldir = 'client_' + re.sub('\W', '', str(call))
					if calldir in entitydir:
						getattr(entity, calldir)()
		db.put(entities)
		if 'updated' in self.body:
			for entity in Entity.gql(
				'WHERE _updated > :updated '
				'AND _owner = :user',
				updated = fromtimestamp(self.body['updated']),
				user = users.get_current_user()):
					self.data(entity)
		else:
			for entity in Entity.all():
				self.data(entity)
		self.out()
		'''
	
	def data(self, data):
		self.result['data'].append(data)
	
	def warn(self, warning):
		self.result['warnings'].append(str(warning))
	
	def error(self, error):
		self.result['errors'].append(str(error))
	
	def out(self):
		self.result['ping'] = ts(datetime.datetime.utcnow())
		data = []
		for item in self.result['data']:
			if 'out' in dir(item):
				data.append(item.out())
			else:
				data.append(item)
		self.result['data'] = data
		self.response.out.write(json.dumps(self.result))
	
	def auth(self):
		self.user = users.get_current_user()
		if not self.user is None:
			self.client = Client.gql('WHERE _owner = :owner', owner = self.user).get()
			if self.client is None:
				self.client = Client()
				self.client.put()

class Entity(PolyModel):
	def __init__(self):
		super(self.__class__, self).__init__(self)
		self.stream = None
		self.server = None
		self.buffer = (ts(datetime.utcnow()) - 1000)
		self.type = (self.__class__.__name__)
	
	creator = db.UserProperty(auto_current_user_add = True)
	owner = db.UserProperty(auto_current_user_add = True)
	updated = db.DateTimeProperty(auto_now = True)
	changes = JsonProperty(default = [])
	data = JsonProperty(default = {})
	
	def execute(self):
		if not self.server is None and not self.stream is None:
			methods = dir(self)
			self.applybuffer([])
			changes = []
			for change in sorted(self.stream, key = attrgetter('_')):
				console.log((self.key()) + ': ' + change['_'])
				if change['_'] < self.server.ping:
					console.log((self.key()) + ' is now ' + self.server.ping)
					change['_'] = self.server.ping
				for property in change:
					if '_client_' + property in methods:
						getattr('_client_' + property, self)(change, data)
				changes.append(change)
			self.applybuffer(changes)
	
	def applybuffer(self, changes):
		changes = sorted(self.changes + changes, key = attrgetter('_'))
		results = []
		data = self.data
		for change in changes:
			if change['_'] < self.buffer:
				data = apply(data, change)
			else:
				results.append(change)
		self.data = data
		self.updated = datetime.utcnow()
		self.changes = results

class Client(Entity):
	def __init__(self):
		super(self.__class__, self).__init__(self)
		self._data = None
		self._server = None
'''
	def client_update(self):
		if self._owner == users.get_current_user():
			self._updated = datetime.datetime.utcnow()
			current = self.dynamic_properties()
			for property in self._data:
				if not '_' in property:
					value = self._data[property]
					old = None
					if property in current:
						old = entity.__getattribute__(name)
					result = apply(old, value)
					if type(result) is type(old):
						self.__setattr__(property, result)
					else:
						if isinstance(result, datetime.datetime):
							self.__setattr__(property, result)
						elif isinstance(result, unicode):
							self.__setattr__(property, db.TextProperty(result))
						else:
							self.__setattr__(property, db.TextProperty(json.dumps(result)))
		else:
			self._server.warning('401: '+str(self.key())+': You are not autorized to modify this object.')
	
	def out(self):
		id = str(self.key())
		if self._data and '_id' in self._data:
			id = self._data['_id']
		out = {
			'_id': id,
			'_key': str(self.key()),
			'_updated': totimestamp(self._updated),
		}
		for name in self.dynamic_properties():
			value = self.__getattribute__(name)
			try:
				out[name] = json.loads(value)
			except:
				try:
					out[name] = totimestamp(value)
				except:
					try:
						out[name] = value.nick()
					except:
						try:
							json.dumps(value)
							out[name] = value
						except:
							out[name] = str(value)
		return out
'''
controller = webapp2.WSGIApplication([
	('/db/.*', actions),
], debug = True)