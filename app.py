from flask import Flask, render_template, request, redirect, url_for, session
import google.generativeai as genai
import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'dsfbhubdsuhfbwiufbhdsf'

# Configure the Google Generative AI API key
GOOGLE_API_KEY = 'AIzaSyCxuCdOtMerepsLXi5G_GLaAdXGhVRgl0M'
genai.configure(api_key=GOOGLE_API_KEY)

# In-memory leaderboard (use a database in production)
leaderboard = []

def generate_questions(difficulty, topics, count):
    prompts = []
    topics_text = ", ".join(topics)
    print(topics)
    for _ in range(count):  # Generate a dynamic number of questions
        try:
            text = f"""
            Create a coding problem in the following format:

            **Problem Description:** 
            * A concise and clear description of the problem.

            **Difficulty:** {difficulty.capitalize()}

            **Topics:** {topics_text}

            **Constraints:**
            * Input limits, time/space complexity constraints, or other relevant restrictions.

            **Input & Output:**
            * Description of the input format and data types.
            * Description of the expected output format and data types.

            **Example:**
            * **Input:** 
              * A specific example of the input format.
            * **Output:** 
              * The corresponding output for the given input.
            * **Explanation:** 
              * A step-by-step explanation of how the output is derived from the input.

            Ensure the problem adheres to the selected difficulty and topics.
            """
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(text)
            question = response.text.strip()
            question = question.replace("**", "").replace("*", "").replace("`", "")  # Clean formatting
            prompts.append(question)
        except Exception as e:
            print(f"Google Generative AI error: {e}")
            return []
    return prompts

def evaluate_code(language, code):
    language_map = {
        'python': 'python3',
        'cpp': 'cpp17',
        'java': 'java',
        'c': 'c',
    }

    client_id = '4732a36711ede8355a7ccb41e7a85435'
    client_secret ='eab3b74ce2d73c5a7767b437e0b61ac38fee0add713699d22d27adfd1a11ff43'

    data = {
        'script': code,
        'language': language_map.get(language, 'cpp17'),
        'versionIndex': '0',
        'clientId': client_id,
        'clientSecret': client_secret
    }

    try:
        response = requests.post('https://api.jdoodle.com/v1/execute', json=data)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        print(f"JDoodle API request error: {e}")
        result = {'error': 'Code execution failed due to a network error.'}

    return result

def assess_code_with_ai(language, code, question):
    print('Processing Code...')
    print('Code:', code)
    
    # If the code is empty, return a message explicitly
    if not code.strip():
        prompt = f"""
        You are a coding expert. Since no code was provided for the following problem, generate a correct solution in {language} with a clear explanation.

        **Problem Description:**
        {question}

        Provide a strictly formatted response:
        1. **Reasoning:** State why the code is empty.
        2. **Solution:** Provide the correct solution along with an explanation.
        """
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            assessment = response.text.strip()
            assessment = assessment.replace("**", "").replace("*", "").replace("`", "")  # Clean formatting
            return f"Evaluation: Code is empty.\n{assessment}"
        except Exception as e:
            print(f"Google Generative AI error: {e}")
            return "AI feedback is unavailable at the moment. Please ensure a solution is provided."

    # If code is provided, evaluate correctness
    prompt = f"""
    You are a coding expert. Your task is to evaluate the given {language} code for the specified problem. Follow these steps strictly:

    1. **If the code is empty**, skip evaluation and instead provide a correct solution with a clear explanation in {language}.
    2. **If the code is not empty**, evaluate it as follows:
       - Verify if the code logically and correctly solves the given problem. If it does not solve the problem or contains errors, explicitly state that it is incorrect and explain why.
       - If the code solves the problem correctly, confirm that it is correct.

    3. Provide detailed feedback on the following aspects:
       - **Correctness:** Is the code solving the problem as described?
       - **Efficiency:** Evaluate the time and space complexity of the solution.
       - **Coding Style:** Assess the readability, maintainability, and adherence to good coding practices.

    **Problem Description:**
    {question}

    **Provided Code:**
    {code}

    Do not include any additional conversation or greetings. Your response should be strictly formatted as follows:
    1. **Evaluation:** Correct/Incorrect
    2. **Reasoning:** Explain why the code is correct or incorrect.
    3. **Solution (if the provided code is incorrect):** Provide a correct solution and explain it.
    """
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        assessment = response.text.strip()
        assessment = assessment.replace("**", "").replace("*", "").replace("`", "")  # Clean formatting
        return assessment
    except Exception as e:
        print(f"Google Generative AI error: {e}")
        return "AI feedback is unavailable at the moment. Please try again later."


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['username'] = request.form['username']
        session['difficulty'] = request.form['difficulty']
        session['topics'] = request.form['topics'].split(',')
        session['question_count'] = int(request.form['questionCount'])
        session['total_time'] = int(request.form['timeDuration']) * 60  # Convert minutes to seconds
        session['start_time'] = time.time()
        return redirect(url_for('challenge'))
    return render_template('index.html')


@app.route('/challenge', methods=['GET', 'POST'])
def challenge():
    if 'username' not in session:
        return redirect(url_for('index'))

    total_time = session.get('total_time', 7200)  # Default to 2 hours (7200 seconds)
    elapsed_time = time.time() - session.get('start_time', time.time())
    remaining_time = int(total_time - elapsed_time)

    if remaining_time <= 0:
        return redirect(url_for('result'))

    # Initialize questions and score tracking
    if 'questions' not in session:
        difficulty = session.get('difficulty', 'Medium')
        topics = session.get('topics', ['Array', 'String'])
        question_count = session.get('question_count', 4)  # Default to 4 questions
        session['questions'] = generate_questions(difficulty, topics, question_count)
        session['current_question'] = 0
        session['correct_answers'] = 0  # Initialize to 0
        session['question_count'] = question_count

    # Check if all questions are completed
    if session['current_question'] >= session['question_count'] or not session['questions']:
        return redirect(url_for('result'))

    question = session['questions'][session['current_question']]

    if request.method == 'POST':
        language = request.form['language']
        code = request.form['code']
        execution_result = evaluate_code(language, code)
        ai_feedback = assess_code_with_ai(language, code, question)

        # Determine if the feedback indicates a correct solution
        is_correct = "Evaluation: Correct" in ai_feedback

        # Increment correct answers if the solution is correct
        if is_correct:
            session['correct_answers'] += 1

        # Move to the next question
        session['current_question'] += 1

        return render_template(
            'feedback.html',
            is_correct=is_correct,
            output=execution_result.get('output', ''),
            error=execution_result.get('error', ''),
            ai_feedback=ai_feedback,
            current_score=(session['correct_answers'] / session['question_count']) * 100
        )

    return render_template(
        'challenge.html',
        question=question,
        question_number=session['current_question'] + 1,
        remaining_time=remaining_time
    )


# Ensure the leaderboard is defined globally and persists across requests
leaderboard = []

@app.route('/result')
def result():
    if 'username' in session:
        # Retrieve total questions and correct answers from session
        total_questions = session.get('question_count', 4)
        correct_answers = session.get('correct_answers', 0)

        # Calculate the final score as a percentage
        score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

        # Format the score to always display up to two decimal places
        formatted_score = "{:.2f}".format(score_percentage)

        # Add the user's result to the leaderboard
        leaderboard.append({'username': session['username'], 'score': formatted_score})

        # Clear the session data to reset for a new challenge
        session.clear()

        # Sort the leaderboard by score in descending order
        sorted_leaderboard = sorted(leaderboard, key=lambda x: float(x['score']), reverse=True)

        # Render the result template with the leaderboard
        return render_template('result.html', leaderboard=sorted_leaderboard)

    # If the user is not in the session, redirect to the index page
    return redirect(url_for('index'))





if __name__ == '__main__':
    app.run(debug=True)
