======================================
Setting up a dev branch for Cerebrum:
======================================


Introduction:
-------------

This recipe is for setting up arch for working with Cerebrum. If you have a
cvs tree, you can keep it; the main idea is to create your own branch of the
"main" archive and set up the necessary synchronization procedures.

A friendly advice is in order -- arch has a rather steep learning curve. Until
you commit for the first time (and your commit ends up in the main cerebrum
archive), do not create huge changes. Get a feeling for what it means to work
with arch, but in such a way that you could potentially start over from
scratch, should you get completely lost in the setup and would like to just
erase everything.

This guide assumes that you are familiar with a number of arch concepts (take
a peek at "hello world meets arch" for a detailed introduction. <URL:
http://www.gnu.org/software/gnu-arch/tutorial/arch.html>).

At USIT we will assume this workflow structure: there is a "main" Cerebrum
archive. It is the "official" repository and it serves as a basis for releases
and there are very few people who can commit to that archive. That archive is
also synchronized against CVS (for as long as CVS exists). The naming scheme
looks thus:

main archive			cerebrum@usit.uio.no--2004
category in the main archive	Cerebrum
branch in that category		Cerebrum--cvs
version in that branch		Cerebrum--cvs--0 

So the fully qualified name of the official version is: ::

    cerebrum@usit.uio.no--2004/Cerebrum--cvs--0
    [      archive           ] 
                               [category]
                               [       branch]
                               [         version]

We will set up an archive called 'ivr@usit.uio.no' that has only read-only
access to the "main" archive. This archive would have a version for cerebrum
development (it can have many) called Cerebrum--ivr--1.0 (i.e. the archive
'ivr@usit.uio.no' will have a *category* "Cerebrum", a branch in that category
called "Cerebrum--ivr", and a version of that branch called
Cerebrum--ivr--1.0).

Graphically (the arrows show the directions in which the changes flow): ::

  cerebrum@usit.uio.no--2004/   Every 12 min      cvs.sf.net:/cvsroot/cerebrum
       Cerebrum--cvs--0       <-------------->           (cvs head)
              ^  |      
              |  +-----------------+               
              |                    |         
              +---------------+    |         
                              |    |         
                              |    |  
                              |    |            
                              |    |            
   hmeland@usit.uio.no--2004/ |    |       ivr@usit.uio.no/
   Cerebrum--doc--1.0         |    +----> Cerebrum--ivr--1.0
   [     version    ]         |           [    version     ]    
                              |
   Cerebrum--main--1.0 <------+      
   [     version     ]         


Please note that arch has really no concept of a "main archive" (i.e. arch has
no concept corresponding directly to "repository" in cvs). As more developers
move to arch, it will make sense for "ivr@usit.uio.no/Cerebrum--ivr--1.0" to
merge in changes from other people's versions.



Setup:
------

* Create your id:

  The standard naming scheme is "name <e-mail>": ::

    tla my-id 'Igor V Rafienko <ivr@usit.uio.no>'

* Create *your* archive: ::

    mkdir ~/arch
    tla make-archive 'ivr@usit.uio.no' ~/arch/ivr@usit.uio.no
    tla my-default-archive 'ivr@usit.uio.no'

  The last step is not necessary, but it makes tla commands less verbose. 

* Register other archives:

  Not all of this is necessary, but you should at least register the "main"
  cerebrum arch archive (the one that is regularily sync'ed against CVS): ::

    tla register-archive \
      'http://www.cerebrum.usit.uio.no/archive/cerebrum@usit.uio.no--2004'
      -> Registering archive: cerebrum@usit.uio.no--2004

    tla register-archive \
      'http://folk.uio.no/hmeland/archives/hmeland@usit.uio.no--2004'
      -> Registering archive: hmeland@usit.uio.no--2004

  Note that these archives are read-only -- you will be able to fetch
  patchsets _from_ these archives, but you will not be able to commit your
  changes to them. More on this later.

* Set up your archive:

  Now you should create your Cerebrum project. In arch terminology you would
  be creating a branch. You can call it whatever you want (that is, both
  category, branch and version parts), but you should really stick
  to some sensible naming scheme: ::

    tla archive-setup Cerebrum--ivr--1.0
    -> creating category ivr@usit.uio.no/Cerebrum
    -> creating branch ivr@usit.uio.no/Cerebrum--ivr
    -> creating version ivr@usit.uio.no/Cerebrum--ivr--1.0

* Set up your branch:

  It makes sense to branch off from the latest revision of the main version
  (it is the easiest way). Note, that it will take quite some time to apply
  all the patchsets: ::

    tla tag cerebrum@usit.uio.no--2004/Cerebrum--cvs--0 Cerebrum--ivr--1.0
    -> Archive caching revision
    -> from import revision: cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--base-0
    -> patching for revision: cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--patch-1
    -> patching for revision: cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--patch-2
    [ ... ]
    -> patching for revision: cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--patch-276
    -> patching for revision: ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0
    -> Made cached revision of  ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0 

  NB! At this point *nothing* has been committed to the 'ivr@usit.uio.no'
  archive. We will do this later.

  Actually, setting of the branch and archive creation can be performed in one
  go: ::

    tla tag --setup cerebrum@usit.uio.no--2004/Cerebrum--cvs--0 \
                    Cerebrum--ivr--1.0

  (--setup tells tag to use archive-setup, if necessary).

* Fetch the code: ::

    tla get Cerebrum--ivr--1.0 ~/work/cerebrum-arch
    -> from archive cached: ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0
    -> making pristine copy
    -> tree version set ivr@usit.uio.no/Cerebrum--ivr--1.0
   
  Now we have the source tree: ::

    cd ~/work/cerebrum-arch
    
* Explore the code:

  This part is optional, but it should give you a feeling of "what's inside" ::

    tla logs -Dsc cerebrum@usit.uio.no--2004/Cerebrum--cvs--0
    -> [ ... bunch of logs, mostly "Update from CVS" ]

  NB! These are the logs from ivr@usit.uio.no archive (they should be
  identical to Cerebrum--cvs--0 up to the tagged version, though)

* First commit:

  Do *NOT* introduce any local changes before this commit.

  Now, the code has been fetched from the main version and dumped into ivr's
  local project tree (~/work/cerebrum-arch). But the code has not yet been
  committed to the ivr@cerebrum.uio.no archive. ::

    cd ~/work/cerebrum-arch
    tla make-log 
    (fiddle with the log)
    tla commit

  The basic setup is finished.



Development cycle:
------------------

Now we are all done and ready to start with our changes. Merges between
different revisions can look something like this: ::

    Cerebrum--cvs--0              Cerebrum--ivr--1.0
           |                             | 
        base-0           +----------> base-0
           |            /                |
        atch-1         /              patch-1
           |          /                  |
          ...        /                  ...
        patch-276 --+    +----------> patch-10
          ...           /                |
        patch-293 -----+                ...
          ...

I.e. every now and then[1] new code is merged to Cerebrum--ivr--1.0 from the
main version. 

*IS IS VERY IMPORTANT* that you stick to these two rules:

  - Do *NOT* merge from Cerebrum--cvs--0 (or any other version) into your
    version (project tree?) when you have your own (local) uncomitted
    changes. Mixing local and merged changes in your revision will make life
    miserable for those who try to merge changes from your version. "tla
    changes" might be helpful here.

  - *Always* commit (to your archive) the changes that you have merged from
    other versions *BEFORE* starting work on your own changes.

Now, let's change some code. The changes are: ::

  tla changes
  -> looking for ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0 to compare with
  -> comparing to ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0
  -> M  Cerebrum/modules/no/hia/mod_sap.py

Let's go and commit. The first step is writing a log: ::

  tla make-log
  -> /hom/ivr/jobb/cerebrum-arch/++log.Cerebrum--ivr--1.0--ivr@usit.uio.no

Now I edit the log (emacs, vi, whatever) and I am ready to commit to my
archive: ::

  tla commit
  -> M  Cerebrum/modules/no/hia/mod_sap.py
  -> update pristine tree 
     (ivr@usit.uio.no/Cerebrum--ivr--1.0--base-0 -> Cerebrum--ivr--1.0--patch-1)
  -> committed ivr@usit.uio.no/Cerebrum--ivr--1.0--patch-1

So, now Cerebrum--ivr--1.0 in the ivr@usit.uio.no archive contains a merging
of Cerebrum--cvs--0 as per patch-276 and the changes in mod_sap.py: ::

  tla revisions --summary
  -> base-0
  ->    tag of cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--patch-276
  -> patch-1
  ->    Attribute renaming in PersonSAPMixin

However, the main version has no Cerebrum--ivr--1.0--patch-1. When I feel
confident enough that it will not break anything, I can can report the changes
to whoever has commit rights to cerebrum@usit.uio.no--2004/Cerebrum--cvs--0
and ask them to merge my changes in.

The next day (BEFORE I start making any changes), I might want to catch up
with the main version: ::

  tla changes 
  -> [ no output ]

Aha, no local changes since last commit. This is good. What new patches have
arrived to the main version since I last merged from it: ::

  tla missing cerebrum@usit.uio.no--2004/Cerebrum--cvs--0
  -> patch-???
  -> patch-???
     ...
  -> patch-???

Ok, so someone changed some code. Let's look at the changes: ::

  tla cat-archive-log cerebrum@usit.uio.no--2004/Cerebrum--cvs--0--patch-???
  -> [ ... ]

The changes are interesting, let us merge them into my project tree: ::

  tla star-merge cerebrum@usit.uio.no--2004/Cerebrum--cvs--0

Note, it is possible to merge only _some_ of the patchsets, but this might not
be very easy or very wise...

Now, in order for the "missing" changes to be available from ivr@usit.uio.no,
we have to commit the result of the star-merge. Or, equally important, before
I can start making local changes, I *must* commit the merged changes (from the
main version).



Opening your work to other cerebrum devs:
-----------------------------------------

In two words -- mirroring archives.

<URL: http://wiki.gnuarch.org/moin.cgi/mini_5fMirroringArchives>





[1] Please note that this synchronization is up to each developer. Some people
like to sync at the start of each work day, other do not. Sometimes it does
not make sense to sync because of the scope of changes in one's code.
