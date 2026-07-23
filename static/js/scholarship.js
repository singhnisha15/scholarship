function clearMultiSelect(id)
{
    let select = document.getElementById(id);

    for(let i=0;i<select.options.length;i++)
    {
        select.options[i].selected = false;
    }
}