
from Message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, MessageGetTaskResult
from TaskComputer import TaskComputer
from TaskConnState import TaskConnState
import time
import cPickle as pickle
import Compress
import os
import struct

class TaskSession:

    ConnectionStateType = TaskConnState

    ##########################
    def __init__( self, conn ):
        self.conn           = conn
        self.taskServer     = None
        self.taskManager    = None
        self.taskComputer   = None
        self.address        = self.conn.transport.getPeer().host
        self.port           = self.conn.transport.getPeer().port
        self.taskId         = 0

    ##########################
    def requestTask( self, taskId, performenceIndex ):
        self.__send( MessageWantToComputeTask( taskId, performenceIndex ) )

    ##########################
    def requestResource( self, taskId, resourceHeader ):
        self.__send( MessageGetResource( taskId, pickle.dumps( resourceHeader ) ) )
        self.conn.fileMode = True

    ##########################
    def sendReportComputedTask( self, subTaskId ):
        self.__send( MessageReportComputedTask( subTaskId ) )

    ##########################
    def interpret( self, msg ):
        if msg is None:
            return

        #print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        self.taskServer.setLastMessage( "<-", time.localtime(), msg, self.address, self.port )

        type = msg.getType()

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

        if type == MessageWantToComputeTask.Type:

            subTaskId, srcCode, extraData, shortDescr, returnAddress, returnPort = self.taskManager.getNextSubTask( msg.taskId, msg.perfIndex )

            if subTaskId != 0:
                self.conn.sendMessage( MessageTaskToCompute( subTaskId, extraData, shortDescr, srcCode, returnAddress, returnPort ) )
            else:
                self.conn.sendMessage( MessageCannotAssignTask( msg.taskId, "No more subtasks in {}".format( msg.taskId ) ) )

        elif type == MessageTaskToCompute.Type:
            self.taskComputer.taskGiven(  msg.subTaskId, msg.sourceCode, msg.extraData, msg.shortDescr, msg.returnAddress, msg.returnPort )
            self.dropped()

        elif type == MessageCannotAssignTask.Type:
            self.taskComputer.taskRequestRejected( msg.taskId, msg.reason )
            self.taskServer.removeTaskHeader( msg.taskId )
            self.dropped()

        elif type == MessageReportComputedTask.Type:
            if msg.subTaskId in self.taskManager.subTask2TaskMapping:
                delay = self.taskManager.acceptResultsDelay( self.taskManager.subTask2TaskMapping[ msg.subTaskId ] )

                if delay == -1.0:
                    self.dropped()
                elif delay == 0.0:
                    self.conn.sendMessage( MessageGetTaskResult( msg.subTaskId, delay ) )
                else:
                    self.conn.sendMessage( MessageGetTaskResult( msg.subTaskId, delay ) )
                    self.dropped()
            else:
                self.dropped()

        elif type == MessageGetTaskResult.Type:
            res = self.taskServer.getWaitingTaskResult( msg.subTaskId )
            if res:
                if msg.delay == 0.0:
                    self.__send( MessageTaskResult( res.subTaskId, res.result ) )
                    self.taskServer.taskResultSent( res.subTaskId )
                else:
                    res.lastSendingTrial    = time()
                    res.delayTime           = msg.delay
                    res.alreadySending      = False
                    self.dropped()

        elif type == MessageTaskResult.Type:
            self.taskManager.computedTaskReceived( msg.subTaskId, msg.result )
            self.dropped()

        elif type == MessageGetResource.Type:
            resFilePath = self.taskManager.prepareResource( msg.subTaskId, pickle.loads( msg.resourceHeader ) )
            #resFilePath  = "d:/src/golem/poc/golemPy/test/res2222221"

            if not resFilePath:
                print "Task {} has no resource".format( msg.subTaskId )
                self.conn.transport.write( struct.pack( "!L", 0 ) )
                self.dropped()
                return

            size = os.path.getsize( resFilePath )

            print "Sendig file size:{}".format( size )

            fh = open( resFilePath, 'rb' )
            data = struct.pack( "!L", size ) + fh.read( 4096 * 1024 )
            while data:
                self.conn.transport.write( data )
                #self.conn.transport.doWrite()
                print "\rSending progress {}                        ".format( float( fh.tell() ) / size ),
                data = fh.read( 4096 * 1024 )
                
            self.dropped()
        elif type == MessageResource.Type:
            self.taskComputer.resourceGiven( msg.subTaskId )
            self.dropped()

    ##########################
    def dropped( self ):
        self.conn.close()
        self.taskServer.removeTaskSession( self )

    def __send( self, msg ):
        #print "Sending to {}:{}: {}".format( self.address, self.port, msg )
        self.conn.sendMessage( msg )
        self.taskServer.setLastMessage( "->", time.localtime(), msg, self.address, self.port )