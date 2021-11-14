﻿using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace ChattingRoom.Core.DB.Models;
#nullable disable
public class User
{
    [Key, MaxLength(16)]
    [DatabaseGenerated(DatabaseGeneratedOption.None)]
    public string Account
    {
        get; set;
    }

    [Required, MaxLength(21)]
    public string Password
    {
        get; set;
    }
    [Required, MaxLength(16)]
    public string NickName
    {
        get; set;
    }
    [Required]
    public DateTime RegisterTime
    {
        get; set;
    }

    public DateTime? LastLoginTime
    {
        get; set;
    }

    public List<Membership> Joined
    {
        get; set;
    } = new();

    [DefaultValue(true)]
    public bool IsActive
    {
        get; set;
    }
}