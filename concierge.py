#Import necessary libraries
import os
import requests
from bs4 import BeautifulSoup
import json
import smtplib
from email.message import EmailMessage
import base64
#Loading the .env
from dotenv import load_dotenv

load_dotenv()

#Creating environment variables for the required services. Is a security best practice to avoid hardcoding sensitive information in the code.
#Serper for we search, Ollama for LLM interactions, and SMTP for sending emails.
#Get the API key from Serper in https://serper.dev/ and set it as an environment variable. For Ollama, you can set the host and model as environment variables as well. For SMTP, set the server, port, username, and password as environment variables.
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

#Update: Create a function that can process the image for the LLM.
def encode_image(image_path):
    #Here we ensure that we can open the file, use it and close it.
    #Using "rb" for read binary, raw bits.
    with open(image_path, "rb") as image_file:
        #We need to convert these raw bytes into text B64 (ASCII) and decode for normal text, for the LLM, then, the text can be sent to the API through JSON.
        return base64.b64encode(image_file.read()).decode('utf-8')

#Important note: each step in the flow will be a function.
def search_web(query:str) -> str:    
    # This function will perform a web search using the given query and return the results as a string
    # You can implement the logic to call a web search API and process the results
    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY is not set in environment variables.")
        return "Error: SERPER_API_KEY is not set in environment variables."
    print("--DEBUG: using Serper API for web search--")
    payload = json.dumps({
        "q": query})
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": SERPER_API_KEY
    }
    try:
        response = requests.post("https://google.serper.dev/search", headers=headers, data=payload)
        print(f"--DEBUG: Serper API response status code: {response.status_code}--")
        print(f"--DEBUG: Serper API response text: {response.text}--")
        response.raise_for_status()
        search_results = response.json()

        #Ensuring that will check if there are organic search results before processing them. If there are no organic search results, it will return a message indicating that no results were found.
        if not search_results.get("organic"):
            print("No organic search results found.")
            return "No organic search results found."
        # Process the search results and return them as a string
        results_str = "Search Results:\n\n"
        #Limiting the number of results to 5 for better readability. You can adjust this number as needed.
        for result in search_results.get("organic", [])[:5]:
            results_str += f"Title: {result.get('title')}\nLink: {result.get('link')}\n\n"
        return results_str
    except requests.RequestException as e:
        print(f"Error occurred while searching web: {e}")
        return f"Error occurred while searching web: {e}"

def browse_website(url:str) -> str:
    # This function will browse the specified website and return the content as a string
    # You can implement the logic to fetch the website content
    print(f"--Tool: Attempting to browse website: {url}--")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            #Do Not Track header to indicate that the user does not want to be tracked by the website. This is a common practice for web scraping to respect user privacy.
            "DNT": "1"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        #Extracting the text content from the website and returning it as a string.
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        if not text:
            print("No text content found on the website.")
            return "No text content found on the website."
        return text[:8000]  # Limiting the content to 8000 characters for better processing. You can adjust this limit as needed.
    except requests.RequestException as e:
        print(f"Error occurred while browsing website: {e}")
        return f"Error occurred while browsing website: {e}"

def send_email(recipient:str, subject:str, body:str) -> str:
    # This function will send an email to the specified recipient with the given subject and body
    # You can implement the logic to send an email using an email API
    print(f"--Tool: Attempting to send email to: {recipient} with subject: {subject}--")
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
        return "Error: SMTP configuration is not fully configured. Cannot send email."
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_USERNAME
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return f"Email sent successfully to {recipient}."
    except Exception as e:
        return f"Error occurred while sending email: {e}"

#Update: Now, the image path is added in the parameters, starting by None in case that an image is not received.
def call_gemma_ollama(prompt:str, output_format:str="json", image_path: str=None) -> str:
    # This function will call the Gemma Ollama API with the given prompt and return the response as a string JSON
    # You can implement the logic to call the API and process the response
    print(f"--Thinking with local Gemma ({OLLAMA_MODEL})--")
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        #This parameter is set to False to get the full response at once instead of streaming it. This can be useful for better processing and handling of the response, especially if the response is expected to be large or if you want to avoid dealing with streaming data.
        "stream": False,
    }

    #Verifying if an image is received:
    if image_path:
        payload["images"]=[encode_image(image_path)]
    if output_format == "json":
        payload["format"] = "json"
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json().get("response", "{}")
    except requests.exceptions.Timeout:
        return f"Error: Ollama API request timed out. The model might be taking too long to generate a response. Please try again later."
    except requests.exceptions.RequestException as e:
        return f"Error: Ollama API request failed with error: {e}"
    except (KeyError, IndexError) as e:
        return f"Error: Failed to parse Ollama API response: {e}"

def run_concierge_agent(goal:str, history:list) -> str:
    # This function will run the concierge agent with the given goal and history
    # You can implement the logic to process the goal and history, and generate a response
    # and will return the response as a string

    #The objective of this prompt is to extract an email address from the user request. The prompt is designed to instruct the LLM to analyze the user request and look for any email addresses. 
    #If an email address is found, it will respond with only the email address. If no email address is found, it will respond with a message indicating that no email address was found. 
    #This prompt can be used as part of the concierge agent's processing to identify and extract email addresses from user requests.
    prompt_extract_email=f"""
        You are an expert at finding email addresses in text.
        Analyze the follwing user request and extract the email address if one is present.
        If you find an email address, respond with ONLY the email address.
        If you do not find an email address, respond with "No email address found".
        User request: "{goal}"
    """

    recipient_email_from_goal = call_gemma_ollama(prompt_extract_email, output_format="text").strip()
    if "@" not in recipient_email_from_goal:
        recipient_email_from_goal = None
    print(f"\n Goal: {goal}\n")

    formated_history = "\n".join(history)
    #Applying the steps:
    #1. Decide what to search for:
    prompt1=f""" You are a helpful concierge agent. Your task is to understand a user's request and generate a concise, effective search query to find the infomation they need. 
    Conversation history:
    ---
    {formated_history}
    ---
    The user's latest request is: "{goal}". 
    
    Based on this request, what is the best, simple search query for Google?
    The query should be 3-5 words.
    Respond with ONLY the search query, without any additional text or explanation.
    """
    search_query = call_gemma_ollama(prompt1, output_format="text").strip().replace('"','')
    search_results = search_web(search_query)
    print(search_results)

    #2. Choose which sites to visit and extract the content:
    prompt2=f""" You a smart web navigator. Your task is to analyze Google search results and select the most promising URLs to find the answer to a user's goal. Avoid generic homepages (like yelp.com or google.com) and prefer specific articles, lists, or maps.

    User's goal: "{goal}"
    Search results: {search_results}
    
    ---
    Based on the user's goal and the search results, which are the top 3 most promising and specific URLs to browse for details?
    Respond with ONLY an list of URLs, one per line.
    """
    #Calling the LLM to get the list of URLs to browse based on the search results and the user's goal.
    urls_to_browse = call_gemma_ollama(prompt2, output_format="text").strip().splitlines()
    #If the LLM does not return any URLs, it will return a brief summary about the findings, not URLs.
    if not urls_to_browse:
        print("--Could not identify promising URLs to browse based on the search results. Returning a brief summary instead.--")
        prompt_summarize_snippets=f""" You are a helpful concierge agent. The web browser is not working, but you have search result snippets.
        User's goal: "{goal}"
        Search results: {search_results}
        ---
        Please provide a summary based *only* on the search result snippets that could help answer the user's goal. If the search results do not provide useful information, respond with "The search results do not provide useful information to answer the user's goal. Also, do not suggest browsing URLs."
        """
        final_summary = call_gemma_ollama(prompt_summarize_snippets, output_format="text")
        print("\n--- Here is your summary --- \n")
        print(final_summary)
        print("\n--- End of summary --- \n")
        return final_summary

    #If the LLM returns URLs, it will browse each URL and extract the content. Then, it will summarize the content of all the URLs to provide a final answer to the user's goal.
    all_website_texts = []
    for url in urls_to_browse:
        website_text = browse_website(url)
        if not website_text.startswith("Error"):
            all_website_texts.append(f"Content from {url}:\n{website_text}\n")
        else:
            print(f"--Error browsing {url}: {website_text}--")
    if not all_website_texts:
        print("--Error: Failed to browse any of the identified URLs. Cannot provide an answer based on website content. Returning a brief summary instead.--")
        prompt_summarize_snippets=f""" You are a helpful concierge agent. The web browser is not working, but you have search result snippets.
        User's goal: "{goal}"
        Search results: {search_results}
        ---
        Please provide a summary based *only* on the search result snippets that could help answer the user's goal. If the search results do not provide useful information, respond with "The search results do not provide useful information to answer the user's goal. Also, do not suggest browsing URLs."
        """
        final_summary = call_gemma_ollama(prompt_summarize_snippets, output_format="text")
        print("\n--- Here is your summary --- \n")
        print(final_summary)
        print("\n--- End of summary --- \n")
        return final_summary 
    
    aggregated_content = "\n\n---\n\n".join(all_website_texts)

    #3. Summarize the content and provide an answer to the user's goal:
    prompt3=f""" You are a meticulous and trustworthy concierge agent. Your primary goal is to provide a clear, concise, and, above all, ACCURATE answer to the user's requuest by synthesizing information from multiple sources.
    User's goal: "{goal}"

    You have gathered information from the following web pages:
    ---
    {aggregated_content}
    ---

    Fact-check and Synthesize: 
    Based on the information above, provide a comprehensive summary that directly answers the user's request.
    Before includin any business or item in your summary, you MUST verify that it meets ALL the specific criteria from the user's request (e.g., hours of operation, location, specific features).
    If you cannot find explicit confirmation that a business meets a criterion, DO NOT include it in the summary. It is better to provide fewer, accurate results than more, inaccurate ones.

    Format your response clearly for the user. If listing places, use bullet points.
    """
    final_summary = call_gemma_ollama(prompt3, output_format="text")
    print("\n--- Here is your summary --- \n")
    print(final_summary)
    print("\n--- End of summary --- \n")
    
    # 4. Decide if an email should be sent and generate its content
    prompt4 = f"""
    You are a highly capable assistant responsible for drafting clear and detailed emails based on a research summary.

    User's original request: "{goal}"

    Here is the final summary of the research, which has been fact-checked to meet the user's criteria:
    ---
    {final_summary}
    ---

    Here is a reminder of the raw text gathered from the websites, which you can use to find details like reservation links:
    ---
    {aggregated_content}
    ---

    Your task is to decide if an email is appropriate to send to the user with this information. If it is, you must draft the email.

    - If the summary contains useful, actionable information (like a list of places, contact info, etc.), then an email should be sent.
    - If the summary is short, conversational, or indicates no results were found, an email is not needed.

    Instructions for the email draft:
    1.  Create a clear subject line that summarizes the content.
    2.  The email body should be a list of the places mentioned in the final summary.
    3.  For each place, provide a brief summary of what it offers and, if you can find one in the raw text, the direct link for reservations.
    4.  Ensure that ONLY information that strictly matches the user's request (e.g., open on a specific day) is included.

    Respond in JSON format.
    If sending, the JSON should be: {{"send_email": true, "subject": "Your requested information", "body": "..."}}
    If not sending, the JSON should be: {{"send_email": false}}

    Example for sending:
    {{
    "send_email": true,
    "subject": "Your requested list of Sushi Restaurants in Seattle",
    "body": "Hello,\n\nHere are the sushi restaurants that match your criteria:\n\n*   **Shiro's Sushi:** A classic spot known for its traditional edomae sushi. Reservations: [https://www.shiros.com/reservations](https://www.shiros.com/reservations)\n\n*   **Sushi Kashiba:** A high-end sushi experience. Reservations: [https://www.sushikashiba.com/](https://www.sushikashiba.com/)"
    }}
    """
    #Calling the LLM to decide if an email should be sent and to generate the email content if needed. The response will be in JSON format, which will indicate whether to send the email and, if so, what the subject and body of the email should be.
    email_decision_str = call_gemma_ollama(prompt4, output_format="json")
    print(email_decision_str)
    print("--FIN DEL COMUNICADO--")
    #Time to verify the possible answers of this calling and take actions.
    try:
        #First, it will try to parse the response from the LLM as JSON. If the parsing is successful, it will check if the "send_email" key is true. If it is true, it will call the send_email function with the recipient email (extracted from the user's goal), subject, and body from the JSON response. If "send_email" is false, it will simply print a message indicating that no email will be sent.
        email_decision = json.loads(email_decision_str)
        if email_decision.get("send_email"):
            subject = email_decision.get("subject")
            body = email_decision.get("body")
            #Before sending the email, it will check if both the subject and body are present. If they are, it will call the send_email function to send the email to the recipient. If either the subject or body is missing, it will print a message indicating that the email cannot be sent due to missing information.
            if all([subject, body]):
                print("\n --I have drafted the following email summary for you ---\n")
                print(f"Subject: {subject}")
                print(f"Body: {body}")
                print("\n--- End of email summary ---\n")
            #Verifying if we have a recipient email extracted from the user's goal. If we do, it will send the email. If not, it will print a message indicating that the email cannot be sent due to the absence of a recipient email address.
                recipient_email = None
                if recipient_email_from_goal != None:
                    #A flag to confirm if the email can be sent to the recipient in recipient_email_from_goal.
                    confirm = input(f"Do you want to send this email to {recipient_email_from_goal}? (y/n): ").strip().lower()
                    if confirm == "y":
                        recipient_email = recipient_email_from_goal
                    #If is not the case, the user has the chance to input an emai address.
                else:
                    confirm = input("Would you like to input an email address to send this information? (y/n): ").strip().lower()
                    if confirm == "y":
                        recipient_email = input("Please enter the email address: ").strip()
                #If all the parameters are completed, time to send the email with the information.
                if recipient_email and recipient_email != None:
                    send_result = send_email(recipient_email, subject, body)
                    print(send_result)
                else:
                    print("--- Okay, I will not send the email. ---")
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"--- Could not determine if an email should be sent due to JSON parsing error: {e} ---")
    
    return final_summary

#5. Final User Interface to run the flow.
def main():
    """
    The main function that runs the terminal application loop.
    """
    #Veryfying if the SERPER_API_KEY exists:
    if not SERPER_API_KEY:
        print("FATAL ERROR: SERPER API KEY evironment variable not set.")
        print("Please get a free key from https://serper.dev and set the variable.")
        return
    
    print("Hello! I am your Local Concierge Agent, powered by a local {OLLAMA_MODEL} model.")
    print("I can remember our conversation and browse multiple sited for you.")
    print("If you configure your SMTP Settings, I can also send emails.")
    print("Make sure Ollama is running in the background.")
    print("Type 'quit' or 'exit' to end the session.")

    #Conversation History variable here:
    conversation_history=[]

    #The permanent loop that is running the agent:
    while True:
        #Update: Now the workflow can admit images.
        user_input = input("\n What would you like to find? (or drop your image here)  \n")
        #Searching in the user goal any signal for finishing the program (Quit or Exit)
        if user_input.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break
        #Evaluating if the user goal includes images:
        if os.path.isfile(user_input):
            print(f"---Analyzing image at '{user_input}' ---")
            #Extracting the image description through LLM.
            image_description=call_gemma_ollama("Describe this image", output_format="text", image_path=user_input)
            #Adding the image to the user goal: The user goal is restricted here.
            user_goal=f"Tell me places where I can find {image_description}"
        #Otherwise, will catch the text.
        else:
            user_goal = user_input

        print("User Goal: {user_goal}")
        agent_summary=run_concierge_agent(user_goal, conversation_history)
        conversation_history.append(f"User: {user_goal}")
        conversation_history.append(f"Agent: {agent_summary}")

if __name__ == "__main__":
    main()