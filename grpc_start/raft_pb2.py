# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: grpc_start/raft.proto
# Protobuf Python Version: 5.27.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    2,
    '',
    'grpc_start/raft.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15grpc_start/raft.proto\x12\x0craft_service\"8\n\x10\x41\x64\x64\x43lientCommand\x12\x11\n\tclient_id\x18\x01 \x01(\x05\x12\x11\n\tclient_ip\x18\x02 \x01(\t\".\n\x19IncrementClientSeqCommand\x12\x11\n\tclient_id\x18\x01 \x01(\x05\",\n\x17\x43hangeLockHolderCommand\x12\x11\n\tclient_id\x18\x01 \x01(\x05\"5\n\x10\x41\x64\x64\x41ppendCommand\x12\x10\n\x08\x66ilename\x18\x01 \x01(\t\x12\x0f\n\x07\x63ontent\x18\x02 \x01(\x0c\"\x17\n\x15\x45xecuteAppendsCommand\"(\n\x13RemoveClientCommand\x12\x11\n\tclient_id\x18\x01 \x01(\x05\"\x8b\x03\n\x08LogEntry\x12\x34\n\nadd_client\x18\x01 \x01(\x0b\x32\x1e.raft_service.AddClientCommandH\x00\x12G\n\x14increment_client_seq\x18\x02 \x01(\x0b\x32\'.raft_service.IncrementClientSeqCommandH\x00\x12\x43\n\x12\x63hange_lock_holder\x18\x03 \x01(\x0b\x32%.raft_service.ChangeLockHolderCommandH\x00\x12\x34\n\nadd_append\x18\x04 \x01(\x0b\x32\x1e.raft_service.AddAppendCommandH\x00\x12>\n\x0f\x65xecute_appends\x18\x05 \x01(\x0b\x32#.raft_service.ExecuteAppendsCommandH\x00\x12:\n\rremove_client\x18\x06 \x01(\x0b\x32!.raft_service.RemoveClientCommandH\x00\x42\t\n\x07\x63ommand\"E\n\nAppendArgs\x12\x10\n\x08leaderID\x18\x01 \x01(\t\x12%\n\x05\x65ntry\x18\x02 \x01(\x0b\x32\x16.raft_service.LogEntry\"7\n\x10RecoveryResponse\x12#\n\x03log\x18\x01 \x03(\x0b\x32\x16.raft_service.LogEntry\"\x14\n\x03Int\x12\r\n\x05value\x18\x01 \x01(\x05\"\x15\n\x04\x42ool\x12\r\n\x05value\x18\x01 \x01(\x08\"\x17\n\x06String\x12\r\n\x05value\x18\x01 \x01(\t\"\x07\n\x05\x45mpty2\x8e\x02\n\x0bRaftService\x12<\n\x0c\x61ppend_entry\x12\x18.raft_service.AppendArgs\x1a\x12.raft_service.Bool\x12<\n\x0fwhere_is_leader\x12\x13.raft_service.Empty\x1a\x14.raft_service.String\x12\x41\n\x0crecover_logs\x12\x11.raft_service.Int\x1a\x1e.raft_service.RecoveryResponse\x12@\n\x13subscribe_to_leader\x12\x14.raft_service.String\x1a\x13.raft_service.Emptyb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'grpc_start.raft_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_ADDCLIENTCOMMAND']._serialized_start=39
  _globals['_ADDCLIENTCOMMAND']._serialized_end=95
  _globals['_INCREMENTCLIENTSEQCOMMAND']._serialized_start=97
  _globals['_INCREMENTCLIENTSEQCOMMAND']._serialized_end=143
  _globals['_CHANGELOCKHOLDERCOMMAND']._serialized_start=145
  _globals['_CHANGELOCKHOLDERCOMMAND']._serialized_end=189
  _globals['_ADDAPPENDCOMMAND']._serialized_start=191
  _globals['_ADDAPPENDCOMMAND']._serialized_end=244
  _globals['_EXECUTEAPPENDSCOMMAND']._serialized_start=246
  _globals['_EXECUTEAPPENDSCOMMAND']._serialized_end=269
  _globals['_REMOVECLIENTCOMMAND']._serialized_start=271
  _globals['_REMOVECLIENTCOMMAND']._serialized_end=311
  _globals['_LOGENTRY']._serialized_start=314
  _globals['_LOGENTRY']._serialized_end=709
  _globals['_APPENDARGS']._serialized_start=711
  _globals['_APPENDARGS']._serialized_end=780
  _globals['_RECOVERYRESPONSE']._serialized_start=782
  _globals['_RECOVERYRESPONSE']._serialized_end=837
  _globals['_INT']._serialized_start=839
  _globals['_INT']._serialized_end=859
  _globals['_BOOL']._serialized_start=861
  _globals['_BOOL']._serialized_end=882
  _globals['_STRING']._serialized_start=884
  _globals['_STRING']._serialized_end=907
  _globals['_EMPTY']._serialized_start=909
  _globals['_EMPTY']._serialized_end=916
  _globals['_RAFTSERVICE']._serialized_start=919
  _globals['_RAFTSERVICE']._serialized_end=1189
# @@protoc_insertion_point(module_scope)
