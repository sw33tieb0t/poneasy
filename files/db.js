(function($, db){
	"use strict";
	var noproto = !({}.__proto__);
	db._proto = function(o){
		function entity(){}
		entity.prototype = o;
		entity = new entity();
		if(noproto) entity.__proto__ = o;
		return entity;
	};
	db._body = {
		creates: {},
		reads: [],
		updates: {},
		deletes: []
	};
	db.store = db.store || {};
	db.Entity = $.extend(function(data){
		if(arguments.length > 1)
			data = Array.prototype.slice.call(arguments, 0);
		if($.type(data) === 'array'){
			$.each(data, function(i, item){
				data[i] = db.Entity(item);
			});
			return data;
		}
		if(db.Entity.is(data))
			return data;
		var id = data;
		if($.type(data) !== 'string'){
			data = data || {};
			id = data._id || data._key || 'new' + (Math.random()+'').replace(/\D/, '');
		}
		var entity = db.store[id];
		if(data._key) id = data._key;
		if(!entity) entity = db.store[id];
		if(!entity){
			entity = db._proto(db.Entity);
			entity.data = {};
		}
		if($.type(data) !== 'object') data = {};
		if(entity._id !== id) entity._id = data._id = id;
		entity.set(data);
		db.store[entity.data._id] = entity;
		return entity;
	}, {
		record: true,
		recording:function(record){
			this.record = record;
			return this;
		},
		is: function(o){
			return (o && o.constructor == db.Entity);
		},
		set: function(data){
			if(!data) return this;
			var difference = false;
			for(var name in data)
				if($.type(this.data[name]) !== $.type(data[name]) ||
					($.type(this.data[name]) === 'string' && this.data[name] !== data[name]) ||
					this.data[name] != data[name]){
						if(!difference) difference = {};
						this.data[name] = difference[name] = data[name];
					}
			if(difference){
				difference._ = new Date().getTime();
				this.fire('change', [difference]);
				if(this.record)
					(db._body.updates[this._id] = db._body.updates[this._id] || []).push(difference);
			}
			return this;
		},
		on: function(type, handler, args){
			if($.type(handler) === 'function'){
				((this._on = this._on || {})[type] = this._on[type] || []).push(handler);
				if(args) handler.apply(this, args);
			}
			return this;
		},
		un: function(type, handler){
			if($.type(handler) === 'function' && this._on && this._on[type]){
				var index = $.inArray(this._on[type], handler);
				if(index != -1){
					this._on[type].splice(index,1);
					if(this._on[type].length == 0)
						delete this._on[type];
				}
			}
			return this;
		},
		fire: function(type, args){
			var entity = this;
			args = args || [];
			if(this._on && this._on[type])
				$.each(this._on[type], function(i, handler){
					if(handler.apply(entity, args) === 'un')
						entity.un(type, handler);
				});
			return this;
		}
	});
	db.sync = function(){
		var body = {ping:new Date().getTime()};
		$.each(db._body.creates, function(){ body.creates = db._body.creates; return false; });
		$.each(db._body.reads, function(){ body.reads = db._body.reads; return false; });
		$.each(db._body.updates, function(){ body.creates = db._body.updates; return false; });
		$.each(db._body.deletes, function(){ body.creates = db._body.deletes; return false; });
		db._body = {
			creates: {},
			reads: [],
			updates: {},
			deletes: []
		};
		var start = new Date().getTime();
		$.ajax({
			url: '/db/',
			type: 'post',
			context: body,
			dataType: 'json',
			processData: false,
			data: JSON.stringify(body),
			success: function(result){
				//console.log(result.ping - (start+(((new Date().getTime())-start)*.5)));
				// $.each(result.data, function(i, entity){

				// });
				console.log(result.data);
				$.each(result.warnings,function(i,w){
					setTimeout(function(){
						console.warn(w);
					}, 0);
				});
				$.each(result.errors,function(i,e){
					setTimeout(function(){
						throw e;
					}, 0);
				});
			},
			complete: function(){
				//console.log(((new Date().getTime())-start)*2);
				setTimeout(function(){
					db.sync();
				}, Math.round(Math.random()*2000)+500);
			}
		});
	};
	db.sync();
})(window.jQuery, window.db = window.EntityDatabase = window.EntityDatabase || {});