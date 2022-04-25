using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using System;
using System.Text;
using OrbCreationExtensions;
using System.Runtime.InteropServices;
using SimpleJSON;
[Serializable]
public class PsynetResponse
{
    public int participant_id;
    public string auth_token;
    public string page_uuid;
    public Answer raw_answer;
    public Metadata metadata;
}
// new version MArch 29 2021
[System.Serializable]
public class PsynetSyncResponse
{
    public int opCode;
    public string data;
    public PsynetSyncResponse(int opCode, string data)
    {
        this.opCode = opCode;
        this.data = data;// "{}";
    }
}
public class WebRequestManager : MonoBehaviour
{
#if UNITY_EDITOR
    public static bool DebugMode = true;
#else
    public static bool DebugMode = false;
#endif
    public static WebRequestManager instance = null;
    public delegate void PsynetSyncRequestEventHandler(PsynetSyncResponse res);
    public static event PsynetSyncRequestEventHandler onPsynetSyncResponse;
    public Hashtable PsynetAnswer;
    public string getPageJsonData;
    public int participantId = -1;
    public string assignmentId = "", PageURL, ResponseURL, debugParticipantsUrl;
    public string authToken = "dummy";
    public string pageUuid = "dummy";
    [DllImport("__Internal")]
    private static extern string GetAssignmentId();
    [DllImport("__Internal")]
    private static extern int GetParticipantId();
    [DllImport("__Internal")]
    private static extern void ReloadPsynetPage();
    
    [DllImport("__Internal")]
    private static extern string GetAuthToken();
    void Awake()
    {
        if (instance == null)
            instance = this;
        else if (instance != this)
            Destroy(gameObject);
        DontDestroyOnLoad(gameObject);
    }
    public IEnumerator Init(int opcode) // Get critical PsyNet information
    {
        if (DebugMode)
        {
            PageURL = "http://localhost:5000/timeline/";
            ResponseURL = "http://localhost:5000/response";
            debugParticipantsUrl = "http://localhost:5000/get_participant_info_for_debug_mode";
            //Debug.Log("Init: Sending GET request to PsyNet...");
            UnityWebRequest initRequest = UnityWebRequest.Get(debugParticipantsUrl);
            yield return initRequest.SendWebRequest();
            if (initRequest.result == UnityWebRequest.Result.ConnectionError | initRequest.downloadHandler is null)
            {
                Debug.LogError("Error sending GET request to PsyNet): " + initRequest.error);
                PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.PAGE_ERROR, "");
                if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
            }
            else
            {
                var jsonData = SimpleJsonImporter.Import(initRequest.downloadHandler.text);
                participantId = int.Parse(jsonData["id"].ToString());
                assignmentId = jsonData["assignment_id"].ToString();
                authToken = jsonData["auth_token"].ToString();
                pageUuid = jsonData["page_uuid"].ToString();
                Debug.Log("Init: participantId: " + participantId + ", authToken: " + authToken + ", assignmentId: " + assignmentId + ", pageUuid: " + pageUuid);
            }
        }
        else
        {
            PageURL = "/timeline/";
            ResponseURL = "/response";
            try
            {
                participantId = GetParticipantId();
                assignmentId = GetAssignmentId();
                authToken = GetAuthToken();
            }
            catch (Exception e)
            {
                PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.PAGE_ERROR, "");
                if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
                Console.WriteLine(e);
                throw;
            }
            Debug.Log("Init: participantId: " + participantId + ", assignmentId: " + assignmentId + ", authToken: " + authToken);
        }
        PsynetSyncResponse res = new PsynetSyncResponse(opcode, participantId.ToString());
        if (onPsynetSyncResponse != null)
            onPsynetSyncResponse(res);
    }
    public IEnumerator GetPage(int opcode) // Get JSON data from PsyNet
    {
        string getPageUrl = PageURL + participantId + "/" + authToken + "?mode=json";
        //Debug.Log("GetPage: Sending GET request to PsyNet...");
        UnityWebRequest getPageRequest = UnityWebRequest.Get(getPageUrl);
        yield return getPageRequest.SendWebRequest();
        if (getPageRequest.result == UnityWebRequest.Result.ConnectionError | getPageRequest.downloadHandler is null)
        {
            Debug.LogError("Error sending GET request to PsyNet: " + getPageRequest.error);
        }
        else
        {
            //Debug.Log("Received from PsyNet: " + getPageRequest.downloadHandler.text);
            getPageJsonData = getPageRequest.downloadHandler.text;
            // Convert to a valid JSON string
            getPageJsonData = getPageJsonData.Replace("\"{", "{").Replace("}\"", "}").Replace("\\", "");
            //Debug.Log("GetPage: getPageJsonData: " + getPageJsonData);
            // Get the page_uuid and auth_token from the response
            var jsonData = SimpleJsonImporter.Import(getPageRequest.downloadHandler.text);
            var attributes = (Hashtable)jsonData["attributes"];
            pageUuid = attributes["page_uuid"].ToString();
            authToken = attributes["auth_token"].ToString();
            yield return new WaitForSeconds(0.1f); // Gives all other processes time to complete before GetInfo is called
            // New version March 29
            PsynetSyncResponse res = new PsynetSyncResponse(opcode, getPageJsonData);
            if (onPsynetSyncResponse != null)
                onPsynetSyncResponse(res);
        }
    }
    public IEnumerator SubmitPage(Answer myAnswer, Metadata myMeta, int opcode)//string answerJson, string metadataJson) // Send JSON data to PsyNet
    {
        //Debug.Log("SubmitPage: Sending POST request to PsyNet...");
        //Debug.Log("participantId: " + participantId + ", pageUuid: " + pageUuid + ", assignmentId: " + assignmentId);
        PsynetResponse myresp = new PsynetResponse();
        myresp.participant_id = participantId;
        myresp.page_uuid = pageUuid;
        myresp.auth_token = authToken;
        myresp.raw_answer = myAnswer; // Island case: empty string, question case: a number string //This is where simple question answer string will go
        myresp.metadata = myMeta; // Island case: This is where current answer object will go
        string json = JsonUtility.ToJson(myresp);
        WWWForm form = new WWWForm();
        form.AddField("json", json);
        //Debug.Log("Sending POST request to PsyNet...");
        UnityWebRequest request = UnityWebRequest.Post(ResponseURL, form);
        yield return request.SendWebRequest();
        if (request.result == UnityWebRequest.Result.ConnectionError)
        {
            Debug.LogError("Error sending POST request to PsyNet: " + request.error);
            PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.PAGE_ERROR, "");
            if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
        }
        else
        {
            //Debug.Log("Received from PsyNet: " + request.downloadHandler.text);
            JSONNode jsonNodeData = JSON.Parse(request.downloadHandler.text);
            bool isUnityPage = (bool)jsonNodeData["page"]["attributes"]["is_unity_page"];
            //Debug.Log("SubmitPage: isUnityPage: " + isUnityPage + ", DebugMode: " + DebugMode);
            if (!isUnityPage && !DebugMode)
            {
                Debug.Log("Reloading PsyNet page...");
                ReloadPsynetPage();
            }
            PsynetSyncResponse res = new PsynetSyncResponse(opcode, isUnityPage.ToString());
            if (onPsynetSyncResponse != null)
                onPsynetSyncResponse(res);
        }
    }
}