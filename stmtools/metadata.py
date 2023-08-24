from typing import TypedDict, Union, Iterable

class STMMetaData(TypedDict, total=False):
    """
    Type annotations for metadata. 
    This is to leave future possibilities to enforce typing. (Aug 24, 2023)
    """
    techniqueId: str
    datasetId: str
    crs: Union[str,int]
    obsDataKeys: Iterable[str]
    auxDataKeys: Iterable[str]
    pntAttribKeys: Iterable[str]
    epochAttribKeys: Iterable[str]
