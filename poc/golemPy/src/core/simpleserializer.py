import json   #debug version
import cPickle as pickle #release version

IS_DEBUG = True

class SimpleSerializerDebug:

    @classmethod
    def dumps( cls, obj ):
        return json.dumps( obj )

    @classmethod
    def loads( cls, data ):
        return json.loads( data )

class SimpleSerializerRelease:

    @classmethod
    def dumps( cls, obj ):
        return pickle.dumps( obj, pickle.HIGHEST_PROTOCOL )

    @classmethod
    def loads( cls, data ):
        return pickle.loads( data )


if IS_DEBUG:
    SimpleSerializer = SimpleSerializerDebug
else:
    SimpleSerializer = SimpleSerializerRelease