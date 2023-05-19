mergeInto(LibraryManager.library, {
  GetAssignmentId: function() {
    returnStr=dallinger.identity.assignmentId;
    var bufferSize = lengthBytesUTF8(returnStr) + 1;
    var buffer = _malloc(bufferSize);
    stringToUTF8(returnStr, buffer, bufferSize);
    return buffer;
  },

  GetPageUUID: function() {
    returnStr=page_uuid;
    var bufferSize = lengthBytesUTF8(returnStr) + 1;
    var buffer = _malloc(bufferSize);
    stringToUTF8(returnStr, buffer, bufferSize);
    return buffer;
  },

  GetParticipantId: function() {
    return dallinger.identity.participantId;
  },

  GetUniqueId: function() {
    returnStr=psynet.uniqueId;
    var bufferSize = lengthBytesUTF8(returnStr) + 1;
    var buffer = _malloc(bufferSize);
    stringToUTF8(returnStr, buffer, bufferSize);
    return buffer;
  },

  ReloadPsynetPage: function() {
    console.log("Reloading page...");
    location.reload();
  }
});
