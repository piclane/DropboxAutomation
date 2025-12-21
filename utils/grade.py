from datetime import date

def calculate_grade(birth_date: date, current_date: date | None = None) -> str:
    """
    生年月日と現在日から学年を計算する関数

    Args:
        birth_date (datetime.date): 生年月日
        current_date (datetime.date, optional): 現在日（Noneの場合は今日）

    Returns:
        str: 学年を表す文字列
    """
    if current_date is None:
        current_date = date.today()

    # 年度を計算する関数
    def get_school_year(target_date: date) -> int:
        if target_date.month >= 4:  # 4月以降
            return target_date.year
        else:  # 1月-3月
            return target_date.year - 1

    # 生まれた年度と現在の年度を取得
    birth_school_year = get_school_year(birth_date)
    current_school_year = get_school_year(current_date)

    # 年度の差を計算
    age_in_school_years = current_school_year - birth_school_year

    # 学年を判定
    if age_in_school_years < 7:
        return "未就学"
    elif 7 <= age_in_school_years <= 12:
        grade = age_in_school_years - 6
        return f"小学校{grade}年生"
    elif 13 <= age_in_school_years <= 15:
        grade = age_in_school_years - 12
        return f"中学校{grade}年生"
    elif 16 <= age_in_school_years <= 18:
        grade = age_in_school_years - 15
        return f"高校{grade}年生"
    else:
        return "高校卒業"

# 使用例
def main() -> None:
    # テストケース
    test_cases = [
        (date(2020, 6, 27), "紬"),
        (date(2018, 11, 26), "真尋"),
    ]

    print("=== 学年計算テスト ===")

    for year in range(2023, 2040):
        current = date(year, 1, 31)  # 2025年8月31日として計算

        print(f"= {year}年 =")

        for birth_date, expected in test_cases:
            result = calculate_grade(birth_date, current)
            print(f"生年月日: {birth_date} → {result} ({expected})")

if __name__ == "__main__":
    main()
