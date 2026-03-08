Developers: Dakshesh Pasala, Ivan Alvarez

Question 1:
- A hard link just creates another name for the same inode whereas a symbolic link
    creates an entirely different file which stores a path to another file/directory.
    Symlinks can cause infinite loops because they can point back to an ancestor directory
    so traversals can repeatedly re-enter the same place. Hard links cannot do this because
    the OS does not allow users to create directory hard links.

Question 2:
- Both fields are necessary because sy_ino is only unique to a given filesystem and st_dev 
    tells you which filesystem the inode belongs to. Therefore, two filesystems can give
    the same inode number. For example imagine a directory structure of a/fs1/one.txt and
    a/fs2/two.txt each with inode number 123. When we visit a/fs1/one.txt if we only record
    the inode then when we visit a/fs2/two.txt, we will skip (detect a cycle) two.txt even 
    though it is a new file.
  
Question 3:
- Our implementation detects that directories are in different filesystems through the -xdev
    flag logic. Stat returns into the stat struct a field 'st_dev' which we store the first 
    occurance of in a global variable 'g_start_dev'. During traversal, we check each 'st_dev' 
    against 'g_start_dev' and skip that file or directory.
  
Question 4:
- The VFS is a kernel abstraction that gives all filesystems the same interface allowing
    Linux to have one tree of multiple filesystems under a common root. It is needed so that
    user programs can get one consistent API regardless of filesystem type. Additionally,
    common logic is shared instead of duplicated. User programs can't just talk to each 
    filesystem driver directly because it would need code for every filesystem making it
    not portable. Additionally, it would require some kernel privilage to talk to the drivers.
