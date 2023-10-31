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
    public string unique_id;
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
        this.data = data;
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
    public string uniqueId = "dummy";
    public string pageUuid = "dummy";
    public bool IsReloaded = false; // track if page was reloaded and do not allow to further submit page in this case.

    [DllImport("__Internal")]
    private static extern string GetAssignmentId();
    [DllImport("__Internal")]
    private static extern int GetParticipantId();
    [DllImport("__Internal")]
    private static extern void ReloadPsynetPage();

    [DllImport("__Internal")]
    private static extern string GetUniqueId();
    
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
            PageURL = "http://localhost:5000/timeline";
            ResponseURL = "http://localhost:5000/response";
            debugParticipantsUrl = "http://localhost:5000/get_participant_info_for_debug_mode";
            //Debug.Log("Init: Sending GET request to PsyNet...");
            //UnityWebRequest initRequest = UnityWebRequest.Get(debugParticipantsUrl);
            using (UnityWebRequest initRequest = UnityWebRequest.Get(debugParticipantsUrl))
            {
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
                    uniqueId = jsonData["unique_id"].ToString();
                    pageUuid = jsonData["page_uuid"].ToString();
                    Debug.Log("Init: participantId: " + participantId + ", assignmentId: " + assignmentId + ", pageUuid: " + pageUuid + ", uniqueId: " + uniqueId);
                }
            }
        }
        else
        {
            PageURL = "/timeline";
            ResponseURL = "/response";
            try
            {
                participantId = GetParticipantId();
                assignmentId = GetAssignmentId();
                uniqueId = GetUniqueId();
            }
            catch (Exception e)
            {
                PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.PAGE_ERROR, "");
                if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
                Console.WriteLine(e);
                throw;
            }
            Debug.Log("Init: participantId: " + participantId + ", assignmentId: " + assignmentId + ", uniqueId: " + uniqueId);
        }
        PsynetSyncResponse res = new PsynetSyncResponse(opcode, uniqueId.ToString());
        IsReloaded = false; // you got a new page so now this page is clearly not reloaded!
        if (onPsynetSyncResponse != null)
            onPsynetSyncResponse(res);
    }
    public IEnumerator GetPage(int opcode) // Get JSON data from PsyNet
    {
        string getPageUrl = PageURL +  "?unique_id=" + uniqueId + "&mode=json";
        //Debug.Log("GetPage: Sending GET request to PsyNet...");
        //UnityWebRequest getPageRequest = UnityWebRequest.Get(getPageUrl);
        Debug.Log("GetPage: participantId: " + participantId + ", assignmentId: " + assignmentId + ", uniqueId: " + uniqueId);
        
        
        using (UnityWebRequest getPageRequest = UnityWebRequest.Get(getPageUrl))
        {
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
                // Get the page_uuid and unique_id from the response
                var jsonData = SimpleJsonImporter.Import(getPageRequest.downloadHandler.text);
                var attributes = (Hashtable)jsonData["attributes"];
                pageUuid = attributes["page_uuid"].ToString();
                uniqueId = attributes["unique_id"].ToString();
                //yield return new WaitForSeconds(0.1f); // Gives all other processes time to complete before GetInfo is called
                PsynetSyncResponse res = new PsynetSyncResponse(opcode, getPageJsonData);
                if (onPsynetSyncResponse != null)
                    onPsynetSyncResponse(res);
            }
        }
        IsReloaded = false; // you got a new page so now this page is clearly not reloaded!
    }
    public IEnumerator SubmitPage(Answer myAnswer, Metadata myMeta, int opcode)//string answerJson, string metadataJson) // Send JSON data to PsyNet
    {
        //Debug.Log("SubmitPage: Sending POST request to PsyNet...");
        //Debug.Log("participantId: " + participantId + ", pageUuid: " + pageUuid + ", assignmentId: " + assignmentId);

        PsynetResponse myresp = new PsynetResponse();
        myresp.participant_id = participantId;
        myresp.page_uuid = pageUuid;
        myresp.unique_id = uniqueId;
        myresp.raw_answer = myAnswer; // Island case: empty string, question case: a number string //This is where simple question answer string will go
        myresp.metadata = myMeta; // Island case: This is where current answer object will go
        string json = JsonUtility.ToJson(myresp);
        WWWForm form = new WWWForm();
        form.AddField("json", json);
        bool is_ok;
        bool isUnityPage= false;
        Debug.Log("SubimtPage: participantId: " + participantId + ", assignmentId: " + assignmentId + ", uniqueId: " + uniqueId);
        if (IsReloaded) // is page reloaded? if so don't allow submission.
        // {
        //     Debug.LogError("Error trying to submit a page while page is already reloaded!: " + " in SubimtPage: participantId: " + participantId + ", assignmentId: " + assignmentId + ", uniqueId: " + uniqueId);
        //     PsynetSyncResponse res2 = new PsynetSyncResponse(Constants.SUBMIT_ERROR, "");
        //     if (onPsynetSyncResponse != null) onPsynetSyncResponse(res2);
        //     return;
        // }

        // ANOTHER ALTERNATIVE INSTEAD OF THROWING AN ERROR
        {
            Debug.LogError("Waning trying to submit a page while page is already reloaded! - I am going to quit and do nothing." + " in SubimtPage: participantId: " + participantId + ", assignmentId: " + assignmentId + ", uniqueId: " + uniqueId);
            yield break;
        }


        using (UnityWebRequest request = UnityWebRequest.Post(ResponseURL, form))
        {
            yield return request.SendWebRequest();
            if (request.result == UnityWebRequest.Result.ConnectionError)
            {
                Debug.LogError("Error sending POST request to PsyNet: " + request.error);
                PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.PAGE_ERROR, "");
                if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
                is_ok = false;
            }
            else
            {
                //Debug.Log("Received from PsyNet: " + request.downloadHandler.text);
                JSONNode jsonNodeData = JSON.Parse(request.downloadHandler.text);
                isUnityPage = (bool)jsonNodeData["page"]["attributes"]["is_unity_page"];
                is_ok = true;
                //Debug.Log("SubmitPage: isUnityPage: " + isUnityPage + ", DebugMode: " + DebugMode);
                
                PsynetSyncResponse res = new PsynetSyncResponse(opcode, isUnityPage.ToString());
                if (onPsynetSyncResponse != null)
                    onPsynetSyncResponse(res);
            }
        }
        if (is_ok && !isUnityPage && !DebugMode)
        {
                    //yield return new WaitForSeconds(0.3f);
                    Debug.Log("Reloading PsyNet page...");
                    IsReloaded=true; // page is reloaded - don't allow to further submit anything untill a new get page arrives.
                    PsynetSyncResponse res1 = new PsynetSyncResponse(Constants.FREEZE, "");
                    if (onPsynetSyncResponse != null) onPsynetSyncResponse(res1);
                    yield return new WaitForSeconds(1f); 
                    ReloadPsynetPage();
        }
    }
}
