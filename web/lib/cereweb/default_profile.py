profile = {
    # default sorting 
    'group': {
        'members': {
            'sort': {
                'union': ('+type', '+name'),
                'inters.': ('+type', '+name'),
                'diff': ('+type', '+name'),
            }
        },
        'list': {
            'sort': ('+name',),
            'columns': ('name', 'description'),
        },
        'search': {
            'wildcards': False
        },
        'view': {
            'mode': 'view' # or edit
        },
    },
    'menu': {
    },
}
