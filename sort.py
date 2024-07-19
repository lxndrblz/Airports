import csv
import operator

def sort_csv_by_code(filename):
    # Read the CSV file
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Skip the header row
        data = list(reader)

    # Sort the data by the "code" column (assuming "code" is at index 0)
    sorted_data = sorted(data, key=operator.itemgetter(0))

    # Write the sorted data back to the same file
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)  # Write the header row
        writer.writerows(sorted_data)

# Usage example
csv_filename = 'citycodes.csv'  # Replace with your actual file name
sort_csv_by_code(csv_filename)
print(f"CSV file '{csv_filename}' sorted by 'code'.")
