import pandas as pd
import pandas_flavor as pf

from typing import Union, Optional, Callable, Tuple, List

@pf.register_dataframe_method
def augment_rolling(
    data: Union[pd.DataFrame, pd.core.groupby.generic.DataFrameGroupBy], 
    date_column: str, 
    value_column: Union[str, list], 
    independent_variable_columns: Optional[Union[str, list]] = None,
    window: Union[int, tuple, list] = 2, 
    window_func: Union[str, list, Tuple[str, Callable]] = 'mean',
    center: bool = False,
    **kwargs,
) -> pd.DataFrame:
    '''Apply one or more rolling functions and window sizes to one or more columns of a DataFrame.
    
    The `augment_rolling` function applies multiple rolling window functions with varying window sizes to specified columns of a DataFrame, considering grouping columns and a datetime column for sorting within each group.
    
    Parameters
    ----------
    data : pd.DataFrame or pd.core.groupby.generic.DataFrameGroupBy
        The input DataFrame or GroupBy object.
    date_column : str
        The `date_column` parameter is the name of the datetime column in the DataFrame by which the data should be sorted within each group.
    value_column : str or list
        The `value_column` parameter is the name of the column(s) in the DataFrame to which the rolling window function(s) should be applied. It can be a single column name or a list of column names.
    window : int or tuple or list
        The `window` parameter in the `augment_rolling` function is used to specify the size of the rolling windows. It can be either an integer or a list of integers. 
        
        - If it is an integer, the same window size will be applied to all columns specified in the `value_column`. 
        
        - If it is a tuple, it will generate windows from the first to the second value (inclusive).
        
        - If it is a list of integers, each integer in the list will be used as the window size for the corresponding column in the `value_column` list.
    window_func : str or list, optional
        The `window_func` parameter in the `augment_rolling` function is used to specify the function(s) to be applied to the rolling windows. It can be a string or a list of strings, where each string represents the name of the function to be applied. Alternatively, it can be a list of tuples, where each tuple contains the name of the function to be applied and the function itself. 
        
        - If it is a string or a list of strings, the same function will be applied to all columns specified in the `value_column`. 
        
        - If it is a list of tuples, each tuple in the list will be used as the function to be applied to the corresponding column in the `value_column` list.
    center : bool, optional
        The `center` parameter in the `augment_rolling` function determines whether the rolling window is centered or not. If `center` is set to `True`, the rolling window will be centered, meaning that the alue at the center of the window will be used as the result. If `False`, the rolling window will not be centered, meaning that the value at the end of the window will be used as the result. The default value is `False`.
    **kwargs : optional
        Additional keyword arguments to be passed to the `pandas.DataFrame.rolling` function.
    
    Returns
    -------
    pd.DataFrame
        The function `augment_rolling` returns a DataFrame with new columns for each applied function, window size, and value column.
    
    Examples
    --------
    ```{python}
    import timetk as tk
    import pandas as pd
    
    df = tk.load_dataset("m4_daily", parse_dates = ['date'])
    df
    ```
    
    ```{python}
    # window = [2,7] yields only 2 and 7
    rolled_df = (
        df
            .groupby('id')
            .augment_rolling(
                date_column = 'date', 
                value_column = 'value', 
                window = [2,7], 
                window_func = ['mean', ('std', lambda x: x.std())]
            )
    )
    rolled_df
    ```
    
    ```{python}
    # window = (1,3) yields 1, 2, and 3
    rolled_df = (
        df
            .groupby('id')
            .augment_rolling(
                date_column = 'date', 
                value_column = 'value', 
                window = (1,3), 
                window_func = ['mean', ('std', lambda x: x.std())]
            )
    )
    rolled_df 
    ```
    
    ```{python}
    # Rolling Regression: Using independent variables
    # Requires: scikit-learn
    from sklearn.linear_model import LinearRegression

    def rolling_regression(df, y, X):
    
        model = LinearRegression()
        X = df[X]  # Extract x values
        y = df[y]  # Extract y values
        model.fit(X, y)
        ret = pd.Series([model.intercept_, model.coef_[0]], index=['Intercept', 'Slope'])
        
        return [ret]
        
    df = pd.DataFrame({
        'id': [1, 1, 1, 2, 2, 2],
        'date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06']),
        'value1': [10, 20, 30, 40, 50, 60],
        'value2': [5, 15, 25, 35, 45, 55],
        'value3': [2, 4, 6, 8, 10, 12]
    })

    # Example to call the function
    result_df = (
        df.groupby('id')
        .augment_rolling(
            date_column='date',
            value_column='value1',
            independent_variable_columns=['value2', 'value3'],
            window=2,
            window_func=[('regression', rolling_regression)]
        )
    )

    result_df


    ```
    '''
    
    
    def rolling_apply(func, series, *args):        
        result = series.rolling(window=window_size, min_periods=window_size, center=center, **kwargs).apply(lambda x: func(x, *args), raw=False)
        return result
    
    def rolling_apply_2(func, df, *args):
        
        results = []
        for start in range(len(df) - window_size + 1):
            window_df = df.iloc[start:start + window_size]
            result = func(window_df, *args, **kwargs)
            results.append(result)
        
        ret = pd.DataFrame(results, index=df.index[window_size - 1:])

        return ret
    
    
    if not isinstance(data, (pd.DataFrame, pd.core.groupby.generic.DataFrameGroupBy)):
        raise TypeError("`data` must be a Pandas DataFrame or GroupBy object.")
        
    if isinstance(value_column, str):
        value_column = [value_column]
        
    if isinstance(window, int):
        window = [window]
    elif isinstance(window, tuple):
        window = list(range(window[0], window[1] + 1))
        
    if isinstance(window_func, (str, tuple)):
        window_func = [window_func]
    
    data_copy = data.copy() if isinstance(data, pd.DataFrame) else data.obj.copy()
    
    if isinstance(data, pd.core.groupby.generic.DataFrameGroupBy):
        group_names = data.grouper.names
        grouped = data_copy.sort_values(by=[*group_names, date_column]).groupby(group_names)
    else: 
        group_names = None
        grouped = [([], data_copy.sort_values(by=[date_column]))]
    
    result_dfs = []
    for _, group_df in grouped:
        for value_col in value_column:
            for window_size in window:
                for func in window_func:
                    if isinstance(func, tuple):
                        func_name, func = func
                        new_column_name = f"{value_col}_rolling_{func_name}_win_{window_size}"
                        
                        if independent_variable_columns:
                            if isinstance(independent_variable_columns, str):
                                independent_variable_columns = [independent_variable_columns]
                            
                            # Here, pass window of rows to the custom function
                            independent_vars = group_df[independent_variable_columns]
                            
                            group_df[new_column_name] = rolling_apply_2(func, group_df, value_col, independent_variable_columns)
                        else:
                            group_df[new_column_name] = rolling_apply(func, group_df[value_col])
                            
                    elif isinstance(func, str):
                        new_column_name = f"{value_col}_rolling_{func}_win_{window_size}"
                        rolling_method = getattr(group_df[value_col].rolling(window=window_size, min_periods=1, center=center, **kwargs), func, None)
                        
                        if rolling_method:
                            group_df[new_column_name] = rolling_method()
                        else:
                            raise ValueError(f"Invalid function name: {func}")
                    
                    else:
                        raise TypeError(f"Invalid function type: {type(func)}")
                    
        result_dfs.append(group_df)

    result_df = pd.concat(result_dfs).sort_index()  # Sort by the original index
    
    return result_df

# Monkey patch the method to pandas groupby objects
pd.core.groupby.generic.DataFrameGroupBy.augment_rolling = augment_rolling
