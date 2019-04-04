from django.db import connection

def search_homestay(term):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM homestay_recommendation.app_homestay WHERE city LIKE '%"+term+"%'")
        row = cursor.fetchall()
    return row