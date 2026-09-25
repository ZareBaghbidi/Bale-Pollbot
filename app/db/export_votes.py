import sqlite3
import pandas as pd

def export_votes():
    conn = sqlite3.connect("pollbot.db")
    try:
        polls_df = pd.read_sql_query("""
        SELECT p.id as poll_id, q.text as question_text
        FROM polls p
        LEFT JOIN questions q ON p.id = q.poll_id
        ORDER BY p.id
        """, conn)

        polls_df['question_text'] = polls_df.apply(
            lambda row: f"Poll {row['poll_id']} (No Text)" if pd.isna(row['question_text']) else row['question_text'],
            axis=1
        )

        users_df = pd.read_sql_query("SELECT chat_id, name FROM users ORDER BY chat_id", conn)
        users_df.set_index('chat_id', inplace=True) # این بخش برای جستجوی سریع نام کاربر خوب است

        votes_df = pd.read_sql_query("SELECT poll_id, user_id, value FROM votes", conn)

        conn.close()

        poll_id_to_question = polls_df.set_index('poll_id')['question_text'].to_dict()

        sorted_poll_ids = polls_df['poll_id'].tolist()

        user_columns = {name: "" for _, name in users_df['name'].items()}


        final_df = pd.DataFrame(index=sorted_poll_ids)

        for user_id, user_name in users_df['name'].items():
            final_df[user_name] = ""

        for _, vote_row in votes_df.iterrows():
            poll_id = vote_row['poll_id']
            user_id = vote_row['user_id']
            value = vote_row['value']

            if poll_id in sorted_poll_ids and user_id in users_df.index:
                user_name = users_df.loc[user_id, 'name']

                if user_name in final_df.columns:
                    pass

        final_data = []
        for poll_id in sorted_poll_ids:
            question_text = poll_id_to_question.get(poll_id, f"Poll {poll_id} (No Text)")
            row_data = {'poll_id': poll_id, 'question_text': question_text}

            for user_id, user_name in users_df['name'].items():
                vote_value = votes_df[(votes_df['poll_id'] == poll_id) & (votes_df['user_id'] == user_id)]['value']
                if not vote_value.empty:
                    row_data[user_name] = vote_value.iloc[0]
                else:
                    row_data[user_name] = ""

            final_data.append(row_data)

        final_df = pd.DataFrame(final_data)

        final_df.sort_values(by='poll_id', inplace=True)

        user_columns_names = list(users_df['name'])
        ordered_columns = ['poll_id', 'question_text'] + user_columns_names
        final_df = final_df[ordered_columns]

        output_filename = "export_votes.xlsx"
        final_df.to_excel(output_filename, index=False)

        print(f"File {output_filename} was successfully created.")

    except Exception as e:
        print(f"Error in processing or saving the file: {e}")
    finally:
        if conn:
            conn.close()