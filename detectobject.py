import cv2
import numpy as np
from collections import defaultdict
from itertools import permutations
from scipy.spatial.distance import euclidean
import pandas as pd
import os

class DetectObject:
    def __init__(self):
        self.detectors = {
            'circle': self.detect_circles,
            'triangle': self.detect_triangles,
            'rectangle': self.detect_rectangles,
            'square': self.detect_squares
        }

    @staticmethod
    def transform_data(input_data):
        """
        transform data from
        input_data = [
            [(1, 2), (3, 4), (5, 6)],
            [(7, 8), (9, 10)]
        ]
        to
        result = [
            [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]],
            [[7.0, 9.0], [8.0, 10.0]]
        ]
        """
        result = []
        for sublist in input_data:
            x_values = [float(t[0]) for t in sublist]
            y_values = [float(t[1]) for t in sublist]
            result.append([x_values, y_values])
        return result

    @staticmethod
    def fill_and_reorder_lists(nested_lists, pad_value=(0, 0)):
        def average_tuples(tuple1, tuple2):
                return ((tuple1[0] + tuple2[0]) / 2, (tuple1[1] + tuple2[1]) / 2)
            
        def reorder(base_list, list2):
            def total_distance(based_list, list2):
                def euclidean_distance(p1, p2):
                    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            
                return sum(euclidean_distance(p1, p2) for p1, p2 in zip(based_list, list2))
            
            all_permutations = permutations(list2)
            min_distance = float('inf')
            best_permutation = None

            for perm in all_permutations:
                dist = total_distance(base_list, perm)
                if dist < min_distance:
                    min_distance = dist
                    best_permutation = perm

            return list(best_permutation)
            
        max_length = 0
        max_index = -1
        for i, inner_list in enumerate(nested_lists):
            if len(inner_list) > max_length:
                max_length = len(inner_list)
                max_index = i
        max_index = max_index
        max_length = max(len(inner_list) for inner_list in nested_lists)
        padded_lists = []
        for inner_list in nested_lists:
            padding_needed = max_length - len(inner_list)
            padding = [pad_value] * padding_needed
            padded_inner_list = inner_list + padding
            padded_lists.append(padded_inner_list)
        
        results = [None] * len(padded_lists)
        results[max_index] = padded_lists[max_index]

        for i in range(0, len(padded_lists)):
            if i != max_index:
                padded_lists[i] = reorder(padded_lists[max_index], padded_lists[i])
            else:
                i += 1
        # substitute (0, 0) with the average of the two adjacent tuples    
        for i in range(0, len(padded_lists)):
            for j in range(0, len(padded_lists[i])):
                if padded_lists[i][j] == (0, 0):
                    if i == 1:
                        padded_lists[i][j] = padded_lists[i + 1][j] 
                    else:
                        padded_lists[i][j] = average_tuples(padded_lists[i - 1][j], padded_lists[i + 1][j])
        return padded_lists
    
    def reorganize_object_coordinates(self, input_list):
        """
        change the list from [[[object(1)x(1), object(2)x(1), object(3)x(1)], [object(1)y(1), object(2)y(1), object(3)y(1)]], [[object(1)x(2), object(2)x(2), object(3)x(2)], [object(1)y(2), object(2)y(2), object(3)y(2)]]]
        to [[[object(1)x(1), object(1)x(2), object(1)x(3)], [object(1)y(1), object(1)y(2), object(1)y(3)]], [[object(2)x(1), object(2)x(2), object(2)x(3)], [object(2)y(1), object(2)y(2), object(2)y(3)]]], 
        """
        input_list = self.transform_data(input_list)
        if not input_list or not input_list[0]:
            return []

        num_frames = len(input_list)
        num_objects = len(input_list[0][0])
        
        result = []
        for obj in range(num_objects):
            x_coords = []
            y_coords = []
            for frame in range(num_frames):
                x_coords.append(input_list[frame][0][obj])
                y_coords.append(input_list[frame][1][obj])
            result.append([x_coords, y_coords])
        
        return result
    
    def time_sequence(self,lst):
        def helper(sub_lst):
            for i in range(len(sub_lst)):
                if isinstance(sub_lst[i], list):
                    helper(sub_lst[i])
                else:
                    sub_lst[i] = i + 1
        helper(lst)
        return lst
    
    def row_data(self, input_list):
        row_data = self.reorganize_object_coordinates(input_list)
        time_sequence = self.time_sequence(self.reorganize_object_coordinates(input_list))
        return row_data, time_sequence
    
    def detect_shapes_in_image(self, image_path, shape_types):
        """
        detect multiple shapes in a single image
        """
        results = {}
        for shape in shape_types:
            if shape not in self.detectors:
                raise ValueError(f"Unsupported shape type: {shape}")
            results[shape] = self.detectors[shape](image_path)
        return results

    def detect(self, image_paths, shape_types):
        """
        detect multiple shapes in multiple images
        """
        results = defaultdict(list)
        
        for path in image_paths:
            image_results = self.detect_shapes_in_image(path, shape_types)
            for shape, centers in image_results.items():
                results[shape].append(centers)
        for shape in results:
            results[shape] = self.fill_and_reorder_lists(results[shape])
        return dict(results)
        
    def detect_circles(self, image_path):
        """
        detect_one_circle
        """
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30, param1=50, param2=30, minRadius=15, maxRadius=50)

        circle_centers = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                circle_centers.append((x, y))
        return circle_centers
    
    def detect_squares(self, image_path):
        pass
    
    def detect_triangles(self, image_path):
        pass
    
    def detect_rectangles(self, image_path):
        pass
    
if __name__ == "__main__":
    def get_image_paths(folder_path):
        if not os.path.exists(folder_path):
            raise ValueError(f"The folder path {folder_path} does not exist.")
        
        all_files = os.listdir(folder_path)
        
        image_files = [f for f in all_files if f.endswith('.jpg') or f.endswith('.png') or f.endswith('.jpeg')]

        image_files.sort()
        
        image_paths = [os.path.join(folder_path, f) for f in image_files]
        
        return image_paths
    
    folder_path = '/Users/dong/Desktop/video/withballframes'
    image_paths = get_image_paths(folder_path)
    

    detector = DetectObject()
    positions_of_circles = detector.detect(image_paths, ['circle'])
    df = pd.DataFrame(positions_of_circles['circle'][:40])
    print(df)
    detector.detect_circles(image_paths[0])